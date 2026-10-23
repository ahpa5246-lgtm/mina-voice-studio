/* Chatterbox upstream model family, GPU cache controls, and honest readiness. */
(() => {
  "use strict";
  const $=q=>document.querySelector(q);
  const localized=(ar,en)=>document.documentElement.lang==="en"?en:ar;
  const model=$("#speechModel"),lang=$("#language"),reference=$("#reference");
  function syncModel(){
    const fast=model.value!=="multilingual-v3";
    if(fast)lang.value="en";
    for(const option of lang.options) option.disabled=fast && option.value!=="en";
    reference.required=fast;
    reference.setAttribute("aria-required",fast?"true":"false");
    $("#modelHint").textContent=fast
      ? localized("Turbo وNano للإنجليزية فقط، ويحتاجان عينة صوتية مرخّصة.",
                  "Turbo and Nano are English-only and need an authorized voice reference.")
      : localized("Multilingual V3 يدعم 23 لغة، وعينة الصوت اختيارية.",
                  "Multilingual V3 supports 23 languages; voice reference is optional.");
  }
  model.addEventListener("change",syncModel);
  syncModel();

  async function refresh(){
    try{
      const response=await fetch("/api/runtime/chatterbox");
      if(!response.ok)throw Error("HTTP "+response.status);
      const info=await response.json();
      $("#runtimeStatus").textContent=info.worker_running
        ? localized("العامل يعمل ويحفظ نموذجًا واحدًا داخل الذاكرة.","Worker active; one model may be cached.")
        : localized("لا يوجد نموذج محمّل حاليًا.","No Chatterbox worker is running.");
    }catch(error){$("#runtimeStatus").textContent=error.message;}
  }
  $("#unloadModel").addEventListener("click",async()=>{
    const button=$("#unloadModel");
    button.disabled=true;
    try{
      const response=await fetch("/api/runtime/chatterbox/unload",{method:"POST"});
      const result=await response.json();
      if(!response.ok)throw Error(result.detail || "HTTP "+response.status);
      await refresh();
    }catch(error){$("#runtimeStatus").textContent=error.message;}
    finally{button.disabled=false;}
  });
  document.querySelector('.nav[data-tab="engines"]').addEventListener("click",refresh);
  refresh();
})();
