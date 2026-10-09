const el = (id) => document.getElementById(id);
const preview = el('preview');
let stream = null;
let peer = null;
let socket = null;
let facing = 'user';
let mirrored = true;
let generation = 0;
let phase = 'idle';
let statsTimer = null;
let connectTimer = null;
let wakeLock = null;
let pendingToken = new URLSearchParams(location.hash.slice(1)).get('pair');
// The secret stays out of HTTP paths, Referer headers, and subsequent history.
history.replaceState(null, '', location.pathname);
preview.dataset.mirror = 'true';

function state(label, nextPhase = phase) {
  phase = nextPhase;
  el('state').textContent = label;
  el('state').dataset.live = String(phase === 'live');
  el('live-label').hidden = phase !== 'live';
  el('start').hidden = phase !== 'idle';
  el('stop').hidden = phase === 'idle';
  el('switch').disabled = phase === 'starting';
  el('quality').disabled = phase !== 'idle';
}

function message(text = '') {
  el('message').textContent = text;
  el('message').hidden = !text;
}

const errors = {
  NotAllowedError: 'Allow camera access in your browser settings, then try again.',
  NotFoundError: 'No camera is available on this device.',
  NotReadableError: 'Another app may be using your camera. Close it and try again.',
  OverconstrainedError: 'This camera cannot use the selected quality. Try 720p.',
};

async function authorize() {
  let response;
  if (pendingToken) {
    response = await fetch('/api/pair', {
      method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ v: 1, token: pendingToken }),
    });
    if (response.ok) pendingToken = null;
  } else {
    response = await fetch('/api/state', { credentials: 'same-origin', cache: 'no-store' });
  }
  const data = await response.json();
  if (!response.ok) throw new Error(data.message || 'Pairing has expired. Restart Kagami on your computer and scan its new QR code.');
  const output = data.output;
  el('output-hint').textContent = `On your computer, select Kagami Virtual Camera in OBS. Output: ${output.width} × ${output.height} · ${output.fps} fps.`;
}

async function release() {
  clearInterval(statsTimer);
  clearTimeout(connectTimer);
  statsTimer = connectTimer = null;
  if (socket) {
    socket.onclose = socket.onerror = socket.onmessage = null;
    socket.close();
    socket = null;
  }
  if (peer) {
    peer.onconnectionstatechange = peer.onicecandidate = null;
    peer.close();
    peer = null;
  }
  if (stream) {
    stream.getTracks().forEach((track) => { track.onended = null; track.stop(); });
    stream = null;
  }
  preview.srcObject = null;
  preview.dataset.visible = 'false';
  el('empty').hidden = false;
  el('stats').textContent = '';
  if (wakeLock) {
    const lock = wakeLock;
    wakeLock = null;
    try { await lock.release(); } catch { /* Lock may already have been released by the OS. */ }
  }
}

function stop(label = 'Ready') {
  generation += 1;
  // Tracks/sockets are released synchronously before the optional wake-lock await.
  void release();
  state(label, 'idle');
}

function fail(error, run) {
  if (run !== generation) return;
  stop('Stopped');
  message(errors[error.name] || error.message || 'Connection lost. Check Kagami on your computer.');
}

async function start() {
  if (phase !== 'idle') return;
  if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia) {
    message('Camera access requires a trusted HTTPS connection. Complete the certificate setup on your computer and phone first.');
    return;
  }
  const run = ++generation;
  state('Connecting', 'starting');
  message();
  try {
    await authorize();
    if (run !== generation) return;
    const height = Number(el('quality').value);
    const captured = await navigator.mediaDevices.getUserMedia({
      audio: false,
      video: { facingMode: { ideal: facing }, width: { ideal: height === 720 ? 1280 : 1920 },
        height: { ideal: height }, frameRate: { ideal: 30, max: 30 } },
    });
    if (run !== generation) { captured.getTracks().forEach((track) => track.stop()); return; }
    stream = captured;
    preview.srcObject = captured;
    await preview.play();
    if (run !== generation) return;
    preview.dataset.visible = 'true';
    el('empty').hidden = true;
    const track = captured.getVideoTracks()[0];
    track.onended = () => fail(new Error('Camera capture ended. Start again when your camera is available.'), run);
    const settings = track.getSettings();
    el('video-spec').textContent = `${settings.height || height}P · ${Math.round(settings.frameRate || 30)}`;
    const pc = peer = new RTCPeerConnection({ iceServers: [], bundlePolicy: 'max-bundle' });
    const transceiver = pc.addTransceiver(track, { direction: 'sendonly', streams: [captured] });
    const codecs = RTCRtpSender.getCapabilities('video')?.codecs.filter((codec) => codec.mimeType.toLowerCase() === 'video/vp8') || [];
    if (!transceiver.setCodecPreferences || !codecs.length) throw new Error('This browser cannot send the VP8 camera format required by Kagami. Use a supported Android Chrome browser.');
    transceiver.setCodecPreferences(codecs);
    const ws = socket = new WebSocket(`${location.protocol === 'https:' ? 'wss:' : 'ws:'}//${location.host}/signal`);
    const remoteIce = [];
    let messages = Promise.resolve();
    pc.onicecandidate = ({ candidate }) => {
      if (run === generation && ws.readyState === WebSocket.OPEN && candidate) {
        ws.send(JSON.stringify({ v: 1, type: 'ice', candidate: candidate.toJSON() }));
      }
    };
    pc.onconnectionstatechange = () => {
      if (run !== generation) return;
      if (pc.connectionState === 'connected') {
        clearTimeout(connectTimer);
        state('Connected', 'live');
        startStats(pc, run);
        if (navigator.wakeLock) {
          navigator.wakeLock.request('screen').then((lock) => {
            if (run === generation) wakeLock = lock;
            else void lock.release();
          }).catch(() => {});
        }
      } else if (pc.connectionState === 'failed') {
        fail(new Error('Video connection failed. Check your local network and the Linux firewall.'), run);
      } else if (pc.connectionState === 'disconnected') {
        state('Reconnecting', 'starting');
        clearTimeout(connectTimer);
        connectTimer = setTimeout(() => fail(new Error('Connection interrupted. Start the camera again to reconnect.'), run), 10000);
      }
    };
    async function receive(data) {
      if (run !== generation) return;
      if (data.v !== 1) throw new Error('Host protocol changed. Refresh this page.');
      if (data.type === 'ready') {
        const offer = await pc.createOffer();
        if (run !== generation) return;
        await pc.setLocalDescription(offer);
        if (run !== generation || ws.readyState !== WebSocket.OPEN) return;
        ws.send(JSON.stringify({ v: 1, type: 'offer', sdp: pc.localDescription.sdp }));
      } else if (data.type === 'answer') {
        await pc.setRemoteDescription({ type: 'answer', sdp: data.sdp });
        for (const candidate of remoteIce.splice(0)) await pc.addIceCandidate(candidate);
      } else if (data.type === 'ice' && data.candidate) {
        if (pc.remoteDescription) await pc.addIceCandidate(data.candidate);
        else {
          if (remoteIce.length >= 256) throw new Error('Host sent too many ICE candidates.');
          remoteIce.push(data.candidate);
        }
      } else if (data.type === 'error') {
        throw new Error(data.message || 'The host could not start the video receiver.');
      }
    }
    ws.onmessage = ({ data }) => {
      messages = messages.then(() => receive(JSON.parse(data))).catch((error) => fail(error, run));
    };
    ws.onerror = () => fail(new Error('Cannot reach the host. Check the trusted certificate, pairing, and local network.'), run);
    ws.onclose = () => fail(new Error('Host connection ended. Check Kagami on your computer and start again.'), run);
    connectTimer = setTimeout(() => fail(new Error('Video setup timed out. Check the host, network interface, and firewall.'), run), 15000);
  } catch (error) {
    fail(error, run);
  }
}

function startStats(pc, run) {
  clearInterval(statsTimer);
  let previous = null;
  statsTimer = setInterval(async () => {
    try {
      const reports = await pc.getStats();
      if (run !== generation) return;
      for (const report of reports.values()) {
        if (report.type === 'outbound-rtp' && report.kind === 'video' && report.bytesSent !== undefined) {
          const bitrate = previous ? (8 * (report.bytesSent - previous.bytes) / (report.timestamp - previous.time)).toFixed(0) : null;
          el('stats').textContent = `${Math.round(report.framesPerSecond || 0)} fps${bitrate ? ` · ${bitrate} kbps` : ''}`;
          previous = { bytes: report.bytesSent, time: report.timestamp };
        }
      }
    } catch { /* Teardown may occur while a stats request is outstanding. */ }
  }, 1000);
}

el('start').addEventListener('click', () => void start());
el('stop').addEventListener('click', () => { stop(); message(); });
el('switch').addEventListener('click', async () => {
  const restart = phase === 'live';
  stop();
  facing = facing === 'user' ? 'environment' : 'user';
  el('source-label').textContent = facing === 'user' ? 'FRONT CAMERA' : 'REAR CAMERA';
  if (restart) await start();
});
el('mirror').addEventListener('click', () => {
  mirrored = !mirrored;
  preview.dataset.mirror = String(mirrored);
  el('mirror').setAttribute('aria-pressed', String(mirrored));
});
window.addEventListener('pagehide', () => stop());
state('Ready', 'idle');
