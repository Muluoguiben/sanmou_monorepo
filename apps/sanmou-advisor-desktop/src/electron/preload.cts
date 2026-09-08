import { contextBridge, ipcRenderer } from "electron";

contextBridge.exposeInMainWorld("sanmou", {
  getRuntimeConfig: () => ipcRenderer.invoke("runtime-config")
});
