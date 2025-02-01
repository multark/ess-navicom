import './index.css'

import { createApp } from 'vue'
import router from './router'
import App from './App.vue'
import store from "./store";
// import mitt from "mitt";

import {
  FrappeUI,
  Button,
  Dialog,
  Card,
  setConfig,
  frappeRequest,
  resourcesPlugin,
} from 'frappe-ui'

let app = createApp(App)

setConfig('resourceFetcher', frappeRequest)
// const emitter = mitt();
// app.config.unwrapInjectedRef = true;
// app.config.globalProperties.emitter = emitter;
app.use(router)
app.use(resourcesPlugin)
app.use(FrappeUI);
app.directive("focus", {
  mounted: (el) => el.focus(),
});
app.component('Button', Button)
app.component('Card', Card)
app.component('Dialog', Dialog)
app.use(store);
app.mount('#app')
