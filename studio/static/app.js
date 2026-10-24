(() => {
"use strict";
const $ = (q) => document.querySelector(q);
const all = (q) => [...document.querySelectorAll(q)];
let locale="ar", engines=[];
const words={
  ar:{queued:"في قائمة الانتظار",running:"المحرك يعالج الصوت، وقد يحتاج تنزيل الأوزان أول مرة",completed:"اكتمل التوليد",failed:"فشلت العملية: ",unavailable:"المحرك غير مهيأ. راجعي صفحة المحركات.",notFound:"لا توجد نماذج مثبتة",ready:"مهيأ (لم يُختبر صوتيًا)",missing:"غير مهيأ",planned:"لم يُبرمج الربط بعد",error:"تعذّر الاتصال بالخادم"},
  en:{queued:"Queued",running:"Audio engine is processing; first use may download model weights",completed:"Audio ready",failed:"Job failed: ",unavailable:"Engine not configured. Check Engines page.",notFound:"No installed models",ready:"Configured (not audio-tested)",missing:"Not configured",planned:"Adapter not implemented",error:"Cannot connect to server"}
};
const t=(key)=>words[locale][key];
const display=(key)=>{all(".nav").forEach((b)=>b.classList.toggle("current",b.dataset.tab===key));all(".tab").forEach((s)=>s.classList.toggle("active",s.id===key));$("#crumb").textContent=$(".nav.current label").textContent;};
function translate(){
 document.documentElement.lang=locale;document.documentElement.dir=locale==="ar"?"rtl":"ltr";
 all("[data-ar]").forEach((node)=>{const value=node.getAttribute("data-"+locale);if(node.tagName==="H1")node.innerHTML=value;else node.textContent=value;});
 $("#crumb").textContent=$(".nav.current label").textContent;
 renderEngines();
}
function renderEngines(){
 const container=$("#engineList");container.textContent="";
 engines.forEach((e)=>{
  const card=document.createElement("div");card.className="card engine-card";
  const title=document.createElement("h3");title.textContent=e.title;
  const info=document.createElement("p");
  info.textContent=e.operation==="speech"?(locale==="ar"?"توليد الكلام متعدد اللغات وعينة صوتية اختيارية.":"Multilingual speech generation with voice reference.") :
   e.operation==="conversion"?(locale==="ar"?"تحويل صوت باستخدام نماذج RVC المثبتة: ":"RVC conversion with installed models: ")+(e.model_count||0):
   e.operation==="provider"?(locale==="ar"?"ربط API محلي؛ تأكدي من تشغيل المحرك وإنتاج الصوت.":"Local API connector; an audio smoke test is still needed.") :
   (locale==="ar"?"ضمن خطة الدمج، ولا يعمل حاليًا.":"Planned adapter; not functional yet.");
  const badge=document.createElement("span");badge.className="tag"+(e.configured?" ok":"");badge.textContent=e.operation==="planned"?t("planned"):e.configured?t("ready"):t("missing");
  card.append(title,info,badge);container.append(card);
 });
}
async function refreshAudioEvidence(){
 const panel=$("#acousticEvidence");
 try{
  const res=await fetch("/api/verification/status",{cache:"no-store"});
  if(!res.ok)throw Error("HTTP "+res.status);
  const body=await res.json();
  panel.replaceChildren();
  for(const info of body.engines){
   const card=document.createElement("div");card.className="card engine-card";
   const title=document.createElement("h3");title.textContent=info.engine.toUpperCase();
   const state=document.createElement("span");state.className="tag"+(info.audio_verified?" ok":"");
   state.textContent=info.audio_verified
     ?(locale==="ar"?"توليد صوت محلي موثّق":"Local WAV verified")
     :(locale==="ar"?"لم يجتز فحص صوت حديث":"No recent passing WAV test");
   const detail=document.createElement("p");
   detail.textContent=info.audio_verified
     ? [info.reported_model, info.duration_seconds+"s",info.realtime_factor+" RTF",
        info.wer===null?"":("WER "+info.wer)].filter(Boolean).join(" · ")
     : (locale==="ar"?"يلزم تشغيل السكربت على GPU والنماذج المثبتة.":"Run the actual model verification on configured hardware.");
   const note=document.createElement("small");
   note.textContent=locale==="ar"
     ?"هذا دليل تشغيل محلي فقط، وليس شهادة بجودة التمثيل."
     :"Local self-reported run, not an independently certified acting score.";
   card.append(title,state,detail,note);panel.append(card);
  }
 }catch(err){panel.textContent="Audio verification unavailable: "+err.message;}
}
async function refresh(){
 try{
  const [a,b]=await Promise.all([fetch("/api/health"),fetch("/api/models")]);if(!a.ok||!b.ok)throw Error("HTTP error");
  engines=(await a.json()).engines;const models=(await b.json()).applio;
  const select=$("#model");select.textContent="";
  if(!models.length){const option=document.createElement("option");option.value="";option.textContent=t("notFound");select.append(option);}
  else models.forEach((m)=>{const option=document.createElement("option");option.value=m.id;option.textContent=m.name;select.append(option);});
  renderEngines();await refreshAudioEvidence();
 }catch(error){$("#engineList").textContent=t("error")+": "+error.message;}
}
const pause=(time)=>new Promise((resolve)=>setTimeout(resolve,time));
async function watch(id,prefix){
 const status=$("#"+prefix+"Status"), player=$("#"+prefix+"Audio"), link=$("#"+prefix+"Download");
 for(let i=0;i<900;i++){
  const response=await fetch("/api/jobs/"+encodeURIComponent(id));if(!response.ok)throw Error("Failed to poll job");
  const job=await response.json();
  if(job.status==="failed")throw Error(job.error||"Unknown error");
  if(job.status==="completed"){status.textContent=t("completed");player.src=job.download;player.hidden=false;link.href=job.download;link.hidden=false;return;}
  status.textContent=t(job.status==="running"?"running":"queued");await pause(2000);
 }
 throw Error("Timed out while checking audio job");
}
async function submit(form,endpoint,prefix,engine){
 const status=$("#"+prefix+"Status"),player=$("#"+prefix+"Audio"),link=$("#"+prefix+"Download"),button=form.querySelector("button[type=submit]");
 if(!form.reportValidity())return;
 if(!engines.some((e)=>e.id===engine&&e.configured)){status.textContent=t("unavailable");display("engines");return;}
 button.disabled=true;player.hidden=true;link.hidden=true;status.textContent=t("queued");
 try{
  const response=await fetch(endpoint,{method:"POST",body:new FormData(form)});
  const data=await response.json();
  if(!response.ok)throw Error(typeof data.detail==="string"?data.detail:JSON.stringify(data.detail));
  await watch(data.id,prefix);
 }catch(error){status.textContent=t("failed")+error.message;}finally{button.disabled=false;}
}
all(".nav").forEach((b)=>b.addEventListener("click",()=>display(b.dataset.tab)));
$("#lang").addEventListener("click",()=>{locale=locale==="ar"?"en":"ar";translate();});
$("#text").addEventListener("input",()=>{$("#counter").textContent=$("#text").value.length+" / 6000";});
$("#counter").textContent=$("#text").value.length+" / 6000";
$("#refresh").addEventListener("click",refresh);
$("#speechForm").addEventListener("submit",(ev)=>{ev.preventDefault();submit(ev.currentTarget,"/api/speech","speech","chatterbox");});
$("#convertForm").addEventListener("submit",(ev)=>{ev.preventDefault();submit(ev.currentTarget,"/api/convert","convert","applio");});
translate();refresh();
})();
