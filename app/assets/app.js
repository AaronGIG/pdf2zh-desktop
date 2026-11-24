const $ = id => document.getElementById(id);
const state = {models: [], jobs: [], file: null, format: 'dual', loadedModel: null};
let jobPollTimer = null;
let jobPollBusy = false;
const jobStatuses = new Map();
const titles = {translate:['文档翻译','保留论文排版，让阅读没有语言边界。'],models:['本地模型','从本地 GGUF 模型获得私密、离线的翻译能力。'],history:['翻译记录','查找本次运行生成的译文。'],settings:['设置','管理应用与本地推理环境。']};
const paths = {
 languages:'<path d="m5 8 6 6M4 14l6-6 2-3M2 5h12M7 2h1M22 22l-5-10-5 10M14 18h6"/>',
 'file-text':'<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6M16 13H8M16 17H8M10 9H8"/>',
 'file-pdf':'<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/><path d="M7 16h2.2a1.6 1.6 0 0 0 0-3.2H7V19M12 19v-6.2h1.6a3.1 3.1 0 0 1 0 6.2H12M17 19v-6h3"/>',
 box:'<path d="m21 8-9-5-9 5 9 5 9-5ZM3 8v8l9 5 9-5V8M12 13v8"/>',
 history:'<path d="M3 12a9 9 0 1 0 3-6.7L3 8"/><path d="M3 3v5h5M12 7v5l4 2"/>',
 shield:'<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10Z"/><path d="m9 12 2 2 4-4"/>',
 settings:'<circle cx="12" cy="12" r="3"/><path d="M19 12a7 7 0 0 0-.1-1l2-1.5-2-3.5-2.4 1a8 8 0 0 0-1.8-1L14.5 2h-5L9 5.8a8 8 0 0 0-1.8 1L5 6 3 9.5 5 11a7 7 0 0 0 0 2l-2 1.5L5 18l2.3-1a8 8 0 0 0 1.8 1l.4 4h5l.4-4a8 8 0 0 0 1.8-1l2.3 1 2-3.5-2-1.5a7 7 0 0 0 .1-1Z"/>',
 upload:'<path d="M12 16V3m-5 5 5-5 5 5M4 15v5a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-5"/>',
 'folder-open':'<path d="m6 14 1.5-5H22l-3 10a2 2 0 0 1-2 1H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h7a2 2 0 0 1 2 2v1"/>',
 x:'<path d="m18 6-12 12M6 6l12 12"/>','arrow-right':'<path d="M5 12h14m-6-6 6 6-6 6"/>',
 sliders:'<path d="M4 21v-7M4 10V3M12 21v-9M12 8V3M20 21v-5M20 12V3M1 14h6M9 8h6M17 16h6"/>',
 sparkles:'<path d="m12 3-1.9 5.1L5 10l5.1 1.9L12 17l1.9-5.1L19 10l-5.1-1.9L12 3ZM5 17v4M3 19h4M19 17v4M17 19h4"/>',
 sigma:'<path d="M18 7V4H6l6 8-6 8h12v-3"/>',layout:'<rect width="18" height="18" x="3" y="3" rx="2"/><path d="M3 9h18M9 21V9"/>',
 'wifi-off':'<path d="m2 2 20 20M8.5 16.5a5 5 0 0 1 7 0M5 13a10 10 0 0 1 3-2M2 8.8a15 15 0 0 1 4-2.5M10.7 5.1a16 16 0 0 1 11.3 3.7M19 13a10 10 0 0 0-2-1.9M12 20h.01"/>',
 plus:'<path d="M12 5v14M5 12h14"/>',info:'<circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 8h.01"/>',
 cpu:'<rect x="5" y="5" width="14" height="14" rx="2"/><rect x="9" y="9" width="6" height="6"/><path d="M9 1v4M15 1v4M9 19v4M15 19v4M1 9h4M1 15h4M19 9h4M19 15h4"/>',
 check:'<path d="m5 12 4 4L19 6"/>','external-link':'<path d="M15 3h6v6M10 14 21 3M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>',
 trash:'<path d="M3 6h18M8 6V4h8v2M19 6l-1 15H6L5 6M10 11v5M14 11v5"/>'
};
function icons(root=document){root.querySelectorAll('[data-icon]').forEach(el=>{el.innerHTML=`<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round">${paths[el.dataset.icon]||paths.box}</svg>`;});}
async function api(method,...args){try{return await window.pywebview.api[method](...args);}catch(error){notify('操作未完成',error.message||String(error),'error');throw error;}}
function notify(title,message,kind='success'){const toast=document.createElement('div');toast.className=`toast ${kind}`;toast.innerHTML='<strong></strong><p></p>';toast.querySelector('strong').textContent=title;toast.querySelector('p').textContent=message;$('toastRegion').appendChild(toast);setTimeout(()=>toast.remove(),kind==='error'?12000:6000);}
function size(bytes){return bytes>1073741824?`${(bytes/1073741824).toFixed(2)} GB`:`${(bytes/1048576).toFixed(1)} MB`;}
function navigate(view){document.querySelectorAll('.view').forEach(el=>el.classList.toggle('active',el.id===`view-${view}`));document.querySelectorAll('.nav-item[data-view]').forEach(el=>el.classList.toggle('active',el.dataset.view===view));$('pageTitle').textContent=titles[view][0];$('pageDescription').textContent=titles[view][1];}
async function refresh(){const next=await api('get_state');Object.assign(state,next);state.format=next.settings.format||'dual';$('targetLanguage').value=next.settings.language||'zh';$('threads').value=next.settings.threads||2;$('threadValue').textContent=$('threads').value;$('contextLength').value=next.settings.context||4096;$('maxPagesPerPart').value=next.settings.maxPagesPerPart??50;$('ocrEnabled').checked=next.settings.ocr!==false;$('translateTableText').checked=next.settings.translateTableText!==false;$('outputPath').textContent=next.outputDir;$('ramInfo').textContent=`可用内存 ${next.resource.ram} GB`;$('coreInfo').textContent=`${next.resource.cores} 线程`;document.querySelectorAll('[data-format]').forEach(el=>el.classList.toggle('selected',el.dataset.format===state.format));renderModels();renderJobs();updateEngine();updateLoading(next);if(!next.loading)$('loadingOverlay').classList.add('hidden');}
function updateLoading(next){if(next.loadingModel)$('loadingName').textContent=next.loadingModel;if(next.loadingDetail)$('loadingStage').textContent=next.loadingDetail;$('loadingElapsed').textContent=next.loadingElapsed?`已用时 ${next.loadingElapsed} 秒，正在等待本地服务响应`:'首次加载可能需要一些时间';if(next.loading)$('loadingOverlay').classList.remove('hidden');}
function updateEngine(){const label=state.loadedModel?`${state.loadedModel} · ${state.device||'CUDA'}`:'等待本地模型';$('engineBadge').classList.toggle('ready',!!state.loadedModel);$('engineBadge').querySelector('span:last-child').textContent=label;$('modelDot').classList.toggle('hidden',!state.loadedModel);$('translationModel').textContent=state.loadedModel?`${state.loadedModel} · ${state.device||'CUDA'} 推理`:'使用本地 GGUF 模型';}
function renderModels(){if(!state.models.length){$('modelList').innerHTML='<div class="empty-list"><i data-icon="box"></i><h3>模型库还是空的</h3><p>点击上方「导入 GGUF 模型」，选择电脑里的模型文件。</p></div>';icons($('modelList'));return;}$('modelList').innerHTML=state.models.map(m=>`<article class="model-item ${state.loadedModel===m.name?'loaded':''}"><div class="model-symbol"><i data-icon="cpu"></i></div><div class="model-copy"><h3>${escapeHtml(m.name)}</h3><p>GGUF · ${size(m.size)}</p><div class="model-state">${state.loadedModel===m.name?'● 已加载 · 可用于文档翻译':''}</div></div><div class="model-actions">${state.loadedModel===m.name?'<button class="button secondary" data-action="unload">卸载模型</button>':`<button class="button primary" data-action="load" data-name="${escapeHtml(m.name)}"><i data-icon="cpu"></i>加载模型</button><button class="icon-button" data-action="remove" data-name="${escapeHtml(m.name)}" title="删除模型"><i data-icon="trash"></i></button>`}</div></article>`).join('');icons($('modelList'));}
function escapeHtml(value){const div=document.createElement('div');div.textContent=value;return div.innerHTML;}
function renderJobs(){const jobs=[...state.jobs].reverse();$('historyList').innerHTML=jobs.length?jobs.map(j=>`<article class="history-item"><i data-icon="file-text"></i><div class="history-copy"><h3>${escapeHtml(j.name)}</h3><p>${escapeHtml(j.detail)} · ${j.progress}%</p></div><span class="job-status">${{completed:'已完成',failed:'失败',running:'翻译中',cancelled:'已取消'}[j.status]}</span>${j.outputs?.length?`<button class="button secondary" data-open="${escapeHtml(j.outputs[0].path)}"><i data-icon="external-link"></i>打开译文</button>`:''}</article>`).join(''):'<div class="empty-list"><i data-icon="history"></i><h3>还没有翻译记录</h3><p>完成的文档会显示在这里。</p></div>';icons($('historyList'));}
async function pollJobs(){
  if(jobPollBusy)return;
  jobPollBusy=true;
  try{
    const next=await window.pywebview.api.get_state();
    state.jobs=next.jobs||[];
    const active=state.jobs.find(j=>j.status==='running')||state.jobs[state.jobs.length-1];
    state.jobs.forEach(job=>{
      const previous=jobStatuses.get(job.id);
      if(previous==='running'&&job.status!=='running'){
        if(job.status==='completed')notify('文档翻译完成',`已生成 ${job.outputs?.[0]?.name||job.name}`,'success');
        if(job.status==='failed')notify('翻译失败',job.detail||'翻译任务失败。','error');
        if(job.status==='cancelled')notify('任务已取消','翻译任务已停止。','info');
      }
      jobStatuses.set(job.id,job.status);
    });
    if(active)showJob(active);
    renderJobs();
    if(!state.jobs.some(j=>j.status==='running')){
      clearInterval(jobPollTimer);
      jobPollTimer=null;
    }
  }catch(error){
    // A transient bridge error should not stop the translation task or freeze the UI.
  }finally{jobPollBusy=false;}
}
function startJobPolling(){
  clearInterval(jobPollTimer);
  jobPollTimer=setInterval(pollJobs,500);
  pollJobs();
}
async function choosePdf(){const file=await api('pick_pdf');if(file)setFile(file);}
function setFile(file){state.file=file;$('emptyFile').classList.add('hidden');$('fileInfo').classList.remove('hidden');const preview=$('pdfPreview');const fallback=$('pdfPreviewFallback');fallback.classList.add('hidden');preview.classList.remove('hidden');preview.src=file.preview;$('pdfName').textContent=file.name;$('pdfMeta').textContent=`${file.pages} 页 · ${size(file.size)}`;$('pdfSample').textContent=file.sample||'未检测到可提取文字，此文档可能是扫描件。';$('textStatus').textContent=file.hasText?'已检测到文本 · 可保留排版翻译':'扫描件 · 可使用 OCR 识别文字';$('completedBox').classList.add('hidden');}
function setupPreviewFallback(){const preview=$('pdfPreview');const fallback=$('pdfPreviewFallback');preview.onload=()=>{preview.classList.remove('hidden');fallback.classList.add('hidden');};preview.onerror=()=>{preview.classList.add('hidden');fallback.classList.remove('hidden');};}
async function waitForModelLoad(name){
  const deadline=Date.now()+420*1000;
  while(Date.now()<deadline){
    await new Promise(resolve=>setTimeout(resolve,1000));
    const next=await api('get_state');
    Object.assign(state,next);
    updateLoading(next);
    renderModels();
    updateEngine();
    if(!next.loading){
      $('loadingOverlay').classList.add('hidden');
      if(next.loadedModel!==name) notify('模型未加载','后端没有完成模型加载，请查看错误提示。','error');
      return next;
    }
  }
  $('loadingOverlay').classList.add('hidden');
  notify('模型加载超时','模型加载超过 420 秒，已停止等待。请检查显存、内存占用与 cuda-server.log。','error');
  return null;
}
async function start(){if(!state.file)return notify('请先选择 PDF','选择需要翻译的文档后再开始。','error');if(!state.loadedModel){navigate('models');return notify('需要本地模型','请导入并加载 GGUF 模型。','error');}const request={path:state.file.path,sourceLanguage:$('sourceLanguage').value,language:$('targetLanguage').value,format:state.format,pages:$('pages').value,threads:Number($('threads').value),maxPagesPerPart:Number($('maxPagesPerPart').value),ocr:$('ocrEnabled').checked,translateTableText:$('translateTableText').checked};const job=await api('start_translation',request);state.jobs.push(job);jobStatuses.set(job.id,job.status);showJob(job);renderJobs();startJobPolling();}
function showJob(job){$('activeJob').classList.toggle('hidden',job.status!=='running');$('completedBox').classList.toggle('hidden',job.status!=='completed');$('jobDetail').textContent=job.detail;$('jobPercent').textContent=`${job.progress}%`;$('jobProgress').style.width=`${job.progress}%`;$('startTranslate').disabled=job.status==='running';if(job.status==='completed'){$('completedName').textContent=job.outputs[0]?.name||job.name;$('openResult').dataset.path=job.outputs[0]?.path||'';}}
window.studioEvent=(event,data)=>{if(event==='notification'){notify(data.title,data.message,data.kind);refresh();}if(event==='model-loading'){updateLoading({...data,loading:true});}if(event==='model-state'&&!data.loading){$('loadingOverlay').classList.add('hidden');refresh();}if(event==='job-updated'){const index=state.jobs.findIndex(j=>j.id===data.id);if(index>=0)state.jobs[index]=data;else state.jobs.push(data);showJob(data);renderJobs();}};
window.addEventListener('pywebviewready',()=>refresh().then(()=>{if(state.jobs.some(j=>j.status==='running'))startJobPolling();}));
setupPreviewFallback();
document.querySelectorAll('[data-view]').forEach(el=>el.addEventListener('click',()=>navigate(el.dataset.view)));
$('choosePdf').onclick=choosePdf;$('changePdf').onclick=choosePdf;$('removePdf').onclick=()=>{state.file=null;$('fileInfo').classList.add('hidden');$('emptyFile').classList.remove('hidden');$('completedBox').classList.add('hidden');};
$('startTranslate').onclick=start;$('cancelJob').onclick=()=>api('cancel_translation');$('threads').oninput=()=>$('threadValue').textContent=$('threads').value;
document.querySelectorAll('[data-format]').forEach(el=>el.onclick=()=>{state.format=el.dataset.format;document.querySelectorAll('[data-format]').forEach(b=>b.classList.toggle('selected',b===el));});
$('importModel').onclick=async()=>{if(await api('pick_model'))refresh();};
$('modelList').onclick=async event=>{const button=event.target.closest('button');if(!button)return;const{action,name}=button.dataset;if(action==='load'){button.disabled=true;$('loadingName').textContent=name;$('loadingStage').textContent='正在准备模型';$('loadingElapsed').textContent='首次加载可能需要一些时间';$('loadingOverlay').classList.remove('hidden');try{await api('load_model',name,Number($('contextLength').value));await waitForModelLoad(name);}catch(error){$('loadingOverlay').classList.add('hidden');notify('模型加载失败',error.message||String(error),'error');}finally{await refresh();}}if(action==='unload')await api('unload_model');if(action==='remove'&&confirm(`从模型库删除 ${name}？原文件不会被删除。`))await api('remove_model',name);if(action!=='load')refresh();};
$('historyList').onclick=e=>{const button=e.target.closest('[data-open]');if(button)api('open_output',button.dataset.open);};
$('openFolder').onclick=()=>api('open_output');$('openResult').onclick=()=>api('open_output',$('openResult').dataset.path);
$('chooseOutput').onclick=async()=>{const r=await api('choose_output_dir');$('outputPath').textContent=r.outputDir;};
document.addEventListener('keydown',e=>{if(e.ctrlKey&&e.key==='Enter')start();});icons();
