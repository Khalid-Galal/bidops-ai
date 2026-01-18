# Page snapshot

```yaml
- generic [ref=e3]:
  - generic [ref=e4]: "[plugin:vite:import-analysis] Failed to resolve import \"@tanstack/react-query-devtools\" from \"src/main.tsx\". Does the file exist?"
  - generic [ref=e5]: D:/Work/intercom/intercom_projects/Hassan/bidops-ai/frontend/src/main.tsx:4:35
  - generic [ref=e6]: "3 | import ReactDOM from \"react-dom/client\"; 4 | import { QueryClient, QueryClientProvider } from \"@tanstack/react-query\"; 5 | import { ReactQueryDevtools } from \"@tanstack/react-query-devtools\"; | ^ 6 | import App from \"./App\"; 7 | import \"./index.css\";"
  - generic [ref=e7]: at TransformPluginContext._formatError (file:///D:/Work/intercom/intercom_projects/Hassan/bidops-ai/frontend/node_modules/vite/dist/node/chunks/dep-BK3b2jBa.js:49258:41) at TransformPluginContext.error (file:///D:/Work/intercom/intercom_projects/Hassan/bidops-ai/frontend/node_modules/vite/dist/node/chunks/dep-BK3b2jBa.js:49253:16) at normalizeUrl (file:///D:/Work/intercom/intercom_projects/Hassan/bidops-ai/frontend/node_modules/vite/dist/node/chunks/dep-BK3b2jBa.js:64307:23) at process.processTicksAndRejections (node:internal/process/task_queues:105:5) at async file:///D:/Work/intercom/intercom_projects/Hassan/bidops-ai/frontend/node_modules/vite/dist/node/chunks/dep-BK3b2jBa.js:64439:39 at async Promise.all (index 4) at async TransformPluginContext.transform (file:///D:/Work/intercom/intercom_projects/Hassan/bidops-ai/frontend/node_modules/vite/dist/node/chunks/dep-BK3b2jBa.js:64366:7) at async PluginContainer.transform (file:///D:/Work/intercom/intercom_projects/Hassan/bidops-ai/frontend/node_modules/vite/dist/node/chunks/dep-BK3b2jBa.js:49099:18) at async loadAndTransform (file:///D:/Work/intercom/intercom_projects/Hassan/bidops-ai/frontend/node_modules/vite/dist/node/chunks/dep-BK3b2jBa.js:51978:27) at async viteTransformMiddleware (file:///D:/Work/intercom/intercom_projects/Hassan/bidops-ai/frontend/node_modules/vite/dist/node/chunks/dep-BK3b2jBa.js:62106:24
  - generic [ref=e8]:
    - text: Click outside, press Esc key, or fix the code to dismiss.
    - text: You can also disable this overlay by setting
    - code [ref=e9]: server.hmr.overlay
    - text: to
    - code [ref=e10]: "false"
    - text: in
    - code [ref=e11]: vite.config.ts
    - text: .
```