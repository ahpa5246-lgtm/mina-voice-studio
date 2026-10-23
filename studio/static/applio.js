/* Native Applio feature UI: no fake successes or generated media. */
(() => {
  "use strict";
  const $ = selector => document.querySelector(selector);
  const translation = (ar,en) => document.documentElement.lang==="en" ? en : ar;
  let models=[];

  async function api(url,options) {
    const response=await fetch(url,options);
    let body={};
    try { body=await response.json(); } catch (_) {}
    if(!response.ok) throw Error(typeof body.detail==="string" ? body.detail : "HTTP "+response.status);
    return body;
  }
  async function refresh() {
    try {
      models=(await api("/api/models")).applio;
      for(const id of ["rvcBatchModel","rvcModelA","rvcModelB"]) {
        const node=$("#"+id), old=node.value;
        node.replaceChildren();
        const blank=document.createElement("option");
        blank.value="";blank.textContent=translation("اختاري نموذجًا","Choose a model");
        node.append(blank);
        for(const model of models) {
          const option=document.createElement("option");
          option.value=model.id;option.textContent=model.name;
          node.append(option);
        }
        if(models.some(m=>m.id===old)) node.value=old;
      }
    } catch(error) {
      $("#rvcBatchStatus").textContent=error.message;
    }
  }
  const pause=ms=>new Promise(resolve=>setTimeout(resolve,ms));
  async function watch(id,status,download,mode) {
    for(let attempt=0;attempt<900;attempt++) {
      const result=await api("/api/jobs/"+encodeURIComponent(id));
      if(result.status==="failed") throw Error(result.error || "Applio failed");
      if(result.status==="completed") {
        if(mode==="blend") {
          if(!result.model?.model_id) throw Error("Applio returned no blended model");
          status.textContent=translation("نجح إنشاء نموذج ","Blended new model ") + result.model.model_id;
          await refresh();
        } else {
          if(!result.download) throw Error("Applio returned no archive");
          download.href=result.download;
          download.hidden=false;
          status.textContent=translation("انتهى التحويل، التنزيل جاهز","Batch conversion complete; archive ready");
        }
        return;
      }
      status.textContent=translation("Applio يعمل...","Processing with Applio...");
      await pause(1700);
    }
    throw Error("Timeout while polling Applio job");
  }
  async function submit(event,mode) {
    event.preventDefault();
    const form=event.currentTarget,button=form.querySelector('button[type="submit"]');
    const status=$("#"+(mode==="blend"?"rvcBlendStatus":"rvcBatchStatus"));
    const download=$("#rvcBatchDownload");
    if(!form.reportValidity()) return;
    if(mode==="batch") {
      const total=$("#rvcBatchAudio").files.length;
      if(total<2||total>8) {
        status.textContent=translation("اختاري 2 إلى 8 ملفات","Choose between 2 and 8 audio files");return;
      }
      download.hidden=true;
    } else if($("#rvcModelA").value===$("#rvcModelB").value) {
      status.textContent=translation("اختاري نموذجين مختلفين","Select two different models");return;
    }
    button.disabled=true;
    status.textContent=translation("جاري رفع الطلب...","Submitting job...");
    try {
      const job=await api("/api/applio/"+(mode==="blend"?"blend":"batch"),
                          {method:"POST",body:new FormData(form)});
      await watch(job.id,status,download,mode);
    } catch(error) {
      status.textContent=translation("فشل: ","Failed: ")+error.message;
    } finally {button.disabled=false;}
  }
  $("#rvcBatchForm").addEventListener("submit",event=>submit(event,"batch"));
  $("#rvcBlendForm").addEventListener("submit",event=>submit(event,"blend"));
  document.querySelector('.nav[data-tab="applio"]').addEventListener("click",refresh);
  refresh();
})();
