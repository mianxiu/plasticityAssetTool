import { defineConfig } from 'vite';
import solidPlugin from 'vite-plugin-solid';
import {randomUUID} from 'node:crypto';

const revision = randomUUID();
export default defineConfig({
  define: {__PAT_UI_BUILD__: JSON.stringify(revision)},
  plugins: [solidPlugin(), {
    name: 'pat-ui-build',
    apply: 'build',
    transformIndexHtml() {
      return [{tag:'meta',attrs:{name:'pat-ui-build',content:revision},injectTo:'head'}];
    },
    generateBundle(_options, bundle) {
      const assets = Object.keys(bundle).filter(name => /\.(js|css)$/.test(name)).sort();
      this.emitFile({type:'asset',fileName:'ui-build.json',source:JSON.stringify({revision,assets})});
    },
  }],
  server: {
    port: 3000,
    proxy: {'/api': 'http://127.0.0.1:15150'},
  },
  // Open edit panels may still need a lazy chunk from the previous build.
  build: {target: 'esnext', emptyOutDir:false},
});
