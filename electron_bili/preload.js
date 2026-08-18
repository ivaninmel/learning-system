const { contextBridge, ipcRenderer } = require('electron');
contextBridge.exposeInMainWorld('learning', {
  search: (keyword) => ipcRenderer.send('search', keyword),
  openUrl: (url) => ipcRenderer.send('open-url', url),
  endLearning: () => ipcRenderer.send('end-learning'),
});
