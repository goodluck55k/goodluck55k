/* Local Chromium screenshots at real desktop and mobile CSS viewport widths. */
const fs = require('node:fs');
const path = require('node:path');
const {pathToFileURL} = require('node:url');
const {chromium} = require('../.tools/node_modules/playwright');

(async () => {
  const root = path.resolve(__dirname, '..');
  const executablePath = 'C:/Program Files/Google/Chrome/Application/chrome.exe';
  const browser = await chromium.launch({executablePath, headless:true});
  const results = [];
  const views=[{name:'local',file:'index.html'}];
  if(fs.existsSync(path.join(root,'previews/github-rendered.html')))views.push({name:'github',file:'github-rendered.html'});
  const works=JSON.parse(fs.readFileSync(path.join(root,'config/profile.json'),'utf8')).works;
  for (const view of views) {
  for (const colorScheme of ['light','dark']) {
    for (const width of [840,375]) {
      const context = await browser.newContext({viewport:{width,height:900}, colorScheme,
        deviceScaleFactor:1, isMobile:width===375, hasTouch:width===375});
      const page = await context.newPage();
      const errors=[];
      page.on('pageerror',e=>errors.push(e.message));
      // The preview has no remote runtime dependencies. Block any accidental network request.
      await page.route(/^https?:/, route => route.abort());
      await page.goto(pathToFileURL(path.join(root,'previews',view.file)).href);
      await page.locator('img').last().waitFor();
      await page.evaluate(async()=>{await Promise.all([...document.images].map(im=>im.decode()));});
      const audit = await page.evaluate(()=>({
        viewport:innerWidth,
        documentWidth:document.documentElement.scrollWidth,
        imageCount:document.images.length,
        images:[...document.images].map(i=>({src:i.currentSrc.split('/').pop(),width:i.clientWidth,
          naturalWidth:i.naturalWidth,ok:i.complete&&i.naturalWidth>0,alt:i.alt})),
        links:[...document.querySelectorAll('a')].map(a=>a.href),
        imageLinks:[...document.querySelectorAll('a')].filter(a=>a.querySelector('img')).map(a=>a.href),
        pictureCount:document.querySelectorAll('picture').length,
        dark:matchMedia('(prefers-color-scheme:dark)').matches,
      }));
      const suffix=`-${colorScheme}${width===375?'-mobile':''}.`;
      const wrongVariant=audit.images.some(i=>!i.src.includes(suffix));
      const missingWorkLink=works.some(w=>!audit.imageLinks.includes(w.url));
      const vectorStats=audit.images.some(i=>i.src.startsWith('stats-')&&i.src.endsWith('.svg'));
      if (audit.viewport!==width||audit.documentWidth>width||audit.images.some(i=>!i.ok)||errors.length||wrongVariant||missingWorkLink||!vectorStats) {
        throw new Error('Preview validation failed: '+JSON.stringify({audit,errors}));
      }
      const output=`previews/${view.name==='local'?'':'github-'}${colorScheme}-${width}.png`;
      await page.screenshot({path:path.join(root,output),fullPage:true});
      results.push({output,view:view.name,colorScheme,width,nativeVectorStats:vectorStats,...audit,errors});
      await context.close();
    }
  }
  }
  await browser.close();
  fs.writeFileSync(path.join(root,'previews/browser-audit.json'),JSON.stringify(results,null,2)+'\n');
  console.log(`${results.length} genuine viewport screenshots passed: native SVG, correct themes, linked Works, 840px / 375px.`);
})().catch(e=>{console.error(e);process.exit(1);});
