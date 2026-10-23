/* Demucs upstream real audio separation. Never display fake stems. */
(() => {
  "use strict";
  const form=document.getElementById("stemsForm");
  const status=document.getElementById("stemsStatus");
  const link=document.getElementById("stemsDownload");
  const local=(ar,en)=>document.documentElement.lang==="en"?en:ar;
  const delay=ms=>new Promise(resolve=>setTimeout(resolve,ms));
  form.addEventListener("submit",async event=>{
    event.preventDefault();
    if(!form.reportValidity())return;
    const button=form.querySelector('button[type="submit"]');
    button.disabled=true;
    link.hidden=true;
    status.textContent=local("جاري رفع التسجيل...","Uploading recording...");
    try{
      const response=await fetch("/api/separate",{method:"POST",body:new FormData(form)});
      const started=await response.json();
      if(!response.ok)throw Error(started.detail||"HTTP "+response.status);
      let completed=false;
      for(let i=0;i<900;i++){
        const result=await fetch("/api/jobs/"+encodeURIComponent(started.id));
        if(!result.ok)throw Error("Job lookup failed");
        const data=await result.json();
        if(data.status==="failed")throw Error(data.error||"Demucs failed");
        if(data.status==="completed"){
          if(!data.download||!data.download.includes("/api/separation/"))throw Error("No real ZIP archive returned");
          link.href=data.download;link.hidden=false;
          status.textContent=local("نجح فصل المسارات. الملف جاهز للتنزيل.","Stems separated. ZIP archive is ready.");
          completed=true;break;
        }
        status.textContent=local("يجري تشغيل Demucs...","Demucs is processing...");
        await delay(1600);
      }
      if(!completed)throw Error("Separation timed out");
    }catch(error){
      status.textContent=local("فشل الفصل: ","Separation failed: ")+error.message;
    }finally{button.disabled=false;}
  });
})();
