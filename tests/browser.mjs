// Actual Chromium getUserMedia + WebRTC peer test. The camera is Chromium's
// synthetic test device; signaling is a browser-local fixture, not GStreamer.
import assert from 'node:assert/strict';
import { createServer } from 'node:http';
import { readFile, mkdir } from 'node:fs/promises';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const { chromium } = createRequire(import.meta.url)('playwright');
const root = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const files = new Map([['/', ['index.html', 'text/html']], ['/app.js', ['app.js', 'text/javascript']], ['/styles.css', ['styles.css', 'text/css']]]);
const output = { width: 1280, height: 720, fps: 30 };
const server = createServer(async (request, response) => {
  if (request.url.startsWith('/api/')) {
    response.writeHead(200, { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' });
    response.end(JSON.stringify({ v: 1, paired: true, output }));
    return;
  }
  const spec = files.get(request.url);
  if (!spec) { response.writeHead(404); response.end(); return; }
  response.writeHead(200, { 'Content-Type': spec[1] });
  response.end(await readFile(path.join(root, 'apps/web-client', spec[0])));
});
await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
const base = `http://127.0.0.1:${server.address().port}`;
// HTTP is confined to this loopback fixture. The shipped host is HTTPS-only.
const browser = await chromium.launch({ headless: true, args: ['--use-fake-ui-for-media-stream', '--use-fake-device-for-media-stream'] });
const context = await browser.newContext({ viewport: { width: 390, height: 844 } });
const page = await context.newPage();
const failures = [];
page.on('pageerror', (error) => failures.push(error.message));
await page.addInitScript(() => {
  const RealPeer = window.RTCPeerConnection;
  const capture = navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);
  window.__tracks = [];
  window.__peers = [];
  navigator.mediaDevices.getUserMedia = async (constraints) => {
    if (window.__denyCamera) throw new DOMException('Denied in test', 'NotAllowedError');
    const stream = await capture(constraints);
    window.__tracks.push(...stream.getTracks());
    if (window.__holdCamera) await new Promise((resolve) => { window.__grantCamera = resolve; });
    return stream;
  };
  window.RTCPeerConnection = class extends RealPeer {
    constructor(options) { super(options); window.__peers.push(this); }
  };
  class LocalSignaler {
    static CONNECTING = 0;
    static OPEN = 1;
    static CLOSED = 3;
    constructor(url) {
      this.url = url;
      this.readyState = 0;
      this.receiver = new RealPeer({ iceServers: [] });
      this.pendingIce = [];
      this.work = Promise.resolve();
      window.__receiver = this.receiver;
      window.__signaler = this;
      this.receiver.onicecandidate = ({ candidate }) => {
        if (candidate) this.deliver({ v: 1, type: 'ice', candidate: candidate.toJSON() });
      };
      this.receiver.ontrack = ({ streams }) => {
        const video = document.createElement('video');
        video.muted = true;
        video.style.display = 'none';
        video.srcObject = streams[0];
        document.body.append(video);
        void video.play();
      };
      setTimeout(() => {
        if (this.readyState === 3) return;
        this.readyState = 1;
        this.onopen?.({});
        this.deliver({ v: window.__hostVersion || 1, type: 'ready', output: { width: 1280, height: 720, fps: 30 } });
      }, 20);
    }
    deliver(data) {
      if (this.readyState === 1) this.onmessage?.({ data: JSON.stringify(data) });
    }
    send(text) {
      this.work = this.work.then(async () => {
        if (this.readyState !== 1) return;
        const data = JSON.parse(text);
        if (data.type === 'offer') {
          await this.receiver.setRemoteDescription({ type: 'offer', sdp: data.sdp });
          for (const candidate of this.pendingIce.splice(0)) await this.receiver.addIceCandidate(candidate);
          await this.receiver.setLocalDescription(await this.receiver.createAnswer());
          this.deliver({ v: 1, type: 'answer', sdp: this.receiver.localDescription.sdp });
        } else if (data.type === 'ice') {
          if (this.receiver.remoteDescription) await this.receiver.addIceCandidate(data.candidate);
          else this.pendingIce.push(data.candidate);
        }
      }).catch((error) => {
        if (this.readyState === 1) this.deliver({ v: 1, type: 'error', message: error.message });
      });
    }
    close() {
      if (this.readyState === 3) return;
      this.readyState = 3;
      this.receiver.onicecandidate = null;
      this.receiver.close();
      this.onclose?.({});
    }
  }
  window.WebSocket = LocalSignaler;
});

const ready = () => page.goto(base + '/#pair=browser-test-fixture');
const ended = () => page.waitForFunction(() => window.__tracks.every((track) => track.readyState === 'ended') && window.__peers.every((peer) => peer.connectionState === 'closed'));
let passed = 0;
async function test(name, run) {
  await ready();
  await run();
  passed += 1;
  console.log(`PASS ${name}`);
}

try {
  await test('responsive layout and secret removed from URL', async () => {
    assert.equal(new URL(page.url()).hash, '');
    for (const width of [320, 390, 768]) {
      await page.setViewportSize({ width, height: 844 });
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
      assert.ok(await page.locator('#start').isVisible());
    }
    await page.setViewportSize({ width: 390, height: 844 });
    await mkdir(path.join(root, 'test-results'), { recursive: true });
    await page.screenshot({ path: path.join(root, 'test-results/phone-client.png'), fullPage: true });
  });
  await test('real VP8 WebRTC sends and decodes synthetic camera frames', async () => {
    await page.locator('#start').click();
    await page.waitForFunction(() => document.querySelector('#state').textContent === 'Connected');
    await page.waitForFunction(async () => {
      for (const stat of (await window.__receiver.getStats()).values()) {
        if (stat.type === 'inbound-rtp' && stat.kind === 'video' && stat.framesDecoded > 3) return true;
      }
      return false;
    });
    const track = await page.evaluate(() => window.__peers[0].getSenders()[0].track.id);
    await page.locator('#mirror').click();
    assert.equal(await page.locator('#preview').getAttribute('data-mirror'), 'false');
    assert.equal(await page.evaluate(() => window.__peers[0].getSenders()[0].track.id), track);
    await page.locator('#stop').click();
    await ended();
    assert.equal(await page.locator('#preview').evaluate((video) => video.srcObject), null);
  });
  await test('switch camera reconnects and closes the previous source', async () => {
    await page.locator('#start').click();
    await page.waitForFunction(() => document.querySelector('#state').textContent === 'Connected');
    await page.locator('#switch').click();
    await page.waitForFunction(() => document.querySelector('#state').textContent === 'Connected' && window.__tracks.length === 2);
    assert.equal(await page.locator('#source-label').textContent(), 'REAR CAMERA');
    assert.equal(await page.evaluate(() => window.__tracks[0].readyState), 'ended');
    await page.locator('#stop').click();
    await ended();
  });
  await test('permission denial leaves no peer or active camera', async () => {
    await page.evaluate(() => { window.__denyCamera = true; });
    await page.locator('#start').click();
    await page.waitForFunction(() => !document.querySelector('#message').hidden);
    assert.match(await page.locator('#message').textContent(), /Allow camera access/);
    assert.equal(await page.evaluate(() => window.__peers.length), 0);
    assert.ok(await page.locator('#start').isVisible());
  });
  await test('stop during pending permission releases a late camera grant', async () => {
    await page.evaluate(() => { window.__holdCamera = true; });
    await page.locator('#start').click();
    await page.waitForFunction(() => typeof window.__grantCamera === 'function');
    await page.locator('#stop').click();
    await page.evaluate(() => window.__grantCamera());
    await ended();
    assert.equal(await page.evaluate(() => window.__peers.length), 0);
  });
  await test('host protocol mismatch tears down capture', async () => {
    await page.evaluate(() => { window.__hostVersion = 99; });
    await page.locator('#start').click();
    await page.waitForFunction(() => !document.querySelector('#message').hidden);
    assert.match(await page.locator('#message').textContent(), /protocol changed/);
    await ended();
  });
  await test('host disconnect stops capture and returns to start control', async () => {
    await page.locator('#start').click();
    await page.waitForFunction(() => document.querySelector('#state').textContent === 'Connected');
    await page.evaluate(() => window.__signaler.close());
    await ended();
    assert.ok(await page.locator('#start').isVisible());
    assert.match(await page.locator('#message').textContent(), /Host connection ended/);
  });
  assert.deepEqual(failures, [], 'No uncaught browser errors');
  console.log(`${passed} browser tests passed. GStreamer/V4L2/Android/OBS are not exercised by this fixture.`);
} finally {
  await context.close();
  await browser.close();
  await new Promise((resolve) => server.close(resolve));
}
