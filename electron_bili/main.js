const { app, BrowserWindow, BrowserView, ipcMain, Menu } = require('electron');
const fs = require('fs');
const path = require('path');

const bridgePath = process.argv[2];
const initialTarget = process.argv[3] || '';
let window;
let browserView;
let activeVideo = null;

function writeEvent(event) {
  fs.mkdirSync(path.dirname(bridgePath), { recursive: true });
  fs.appendFileSync(bridgePath, `${JSON.stringify(event)}\n`, 'utf8');
}

function searchUrl(keyword) {
  return `https://search.bilibili.com/all?keyword=${encodeURIComponent(keyword)}`;
}

function openTarget(target) {
  const url = /^https?:\/\//.test(target) ? target : searchUrl(target);
  loadApproved(url);
}

function isVideoUrl(url) {
  return url.includes('bilibili.com/video/');
}

function loadApproved(url) {
  browserView.webContents.loadURL(url);
}

async function getVideoTitle(url) {
  const match = url.match(/\/video\/(BV[\w]+)/i);
  if (!match) return '未识别标题的视频';
  try {
    const response = await fetch(`https://api.bilibili.com/x/web-interface/view?bvid=${match[1]}`);
    const data = await response.json();
    return data?.data?.title || '未识别标题的视频';
  } catch {
    return '未识别标题的视频';
  }
}

function finishVideo() {
  if (!activeVideo) return;
  writeEvent({ action: '学习结束', title: activeVideo.title || '未命名视频', url: activeVideo.url, duration: Math.floor((Date.now() - activeVideo.startedAt) / 1000) });
  activeVideo = null;
}

function resizeView() {
  if (!window || !browserView) return;
  const [width, height] = window.getContentSize();
  browserView.setBounds({ x: 0, y: 74, width, height: Math.max(1, height - 74) });
}

function lockSearchPage() {
  const script = `
    if (location.hostname.includes('bilibili.com') && location.pathname.includes('/all')) {
      const disablePreview = () => document.querySelectorAll('video').forEach((video) => {
        video.pause(); video.removeAttribute('autoplay'); video.muted = true; video.style.display = 'none';
      });
      disablePreview();
      new MutationObserver(disablePreview).observe(document.documentElement, { childList: true, subtree: true });
      document.addEventListener('mouseenter', disablePreview, true);
      document.addEventListener('mouseover', disablePreview, true);
    }
  `;
  browserView.webContents.insertCSS('header,.bili-header,.ad-report,.video-card-ad-small{display:none!important}');
  browserView.webContents.executeJavaScript(script).catch(() => {});
}

function createWindow() {
  window = new BrowserWindow({
    width: 1220,
    height: 820,
    minWidth: 820,
    minHeight: 580,
    title: 'B站专注学习',
    backgroundColor: '#f3f7f4',
    autoHideMenuBar: true,
    menuBarVisible: false,
    webPreferences: { preload: path.join(__dirname, 'preload.js'), contextIsolation: true, nodeIntegration: false },
  });
  window.loadFile(path.join(__dirname, 'index.html'));
  browserView = new BrowserView({ webPreferences: { contextIsolation: true, nodeIntegration: false } });
  browserView.webContents.setUserAgent('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36');
  window.setBrowserView(browserView);
  resizeView();
  window.on('resize', resizeView);
  window.on('close', finishVideo);
  browserView.webContents.setWindowOpenHandler(({ url }) => {
    loadApproved(url);
    return { action: 'deny' };
  });
  browserView.webContents.on('did-navigate', (_, url) => trackUrl(url));
  browserView.webContents.on('did-navigate-in-page', (_, url) => trackUrl(url));
  browserView.webContents.on('did-finish-load', lockSearchPage);
  browserView.webContents.on('page-title-updated', (_, title) => {
    if (activeVideo && title.trim()) {
      activeVideo.title = title.replace(/_哔哩哔哩_bilibili/gi, '').trim();
      if (!activeVideo.titleLogged) {
        writeEvent({ action: '开始学习', title: activeVideo.title, url: activeVideo.url });
        activeVideo.titleLogged = true;
      }
    }
  });
  if (/^https?:\/\//.test(initialTarget)) openTarget(initialTarget);
  else if (initialTarget.trim()) {
    writeEvent({ action: '搜索', keyword: initialTarget.trim() });
    openTarget(initialTarget);
  }
}

function trackUrl(url) {
  if (!isVideoUrl(url)) return;
  if (activeVideo && activeVideo.url === url) return;
  finishVideo();
  activeVideo = { url, title: '', titleLogged: false, startedAt: Date.now() };
  getVideoTitle(url).then((title) => {
    if (!activeVideo || activeVideo.url !== url || activeVideo.titleLogged) return;
    activeVideo.title = title;
    activeVideo.titleLogged = true;
    writeEvent({ action: '开始学习', title, url });
  });
}

ipcMain.on('search', (_, keyword) => {
  if (!keyword.trim()) return;
  writeEvent({ action: '搜索', keyword: keyword.trim() });
  openTarget(keyword.trim());
});
ipcMain.on('open-url', (_, url) => { if (url.trim()) openTarget(url.trim()); });
ipcMain.on('end-learning', finishVideo);

app.whenReady().then(() => { Menu.setApplicationMenu(null); createWindow(); });
app.on('window-all-closed', () => app.quit());
