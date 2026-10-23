/* Real local audio workflows; not a demo or simulated audio. */
(() => {
"use strict";
const $ = (q) => document.querySelector(q);
const text = (ar,en) => document.documentElement.lang === "en" ? en : ar;
let toolStates = [];
let voices = [];
const fmtError = (error) => error instanceof Error ? error.message : String(error);
async function api(path,options){
  const response = await fetch(path,options);
  let json = {};
  try { json = await response.json(); } catch (_) { }
  if(!response.ok) throw Error(typeof json.detail === "string" ? json.detail : "HTTP "+response.status);
  return json;
}
const sleep = (ms) => new Promise(resolve=>setTimeout(resolve,ms));
async function watchJob(id, statusNode, audioNode, linkNode, textNode){
  for(let k=0;k<600;k++){
    const result = await api("/api/jobs/"+encodeURIComponent(id));
    if(result.status==="failed") throw Error(result.error || "Unknown engine error");
    if(result.status==="completed"){
      statusNode.textContent=text("انتهت المعالجة بنجاح","Completed successfully");
      if(result.training) statusNode.textContent += " — "+result.training.model_name+" ("+result.training.checkpoint_count+" checkpoints)";
      if(result.download&&audioNode&&linkNode){
        audioNode.src=result.download;audioNode.hidden=false;
        linkNode.href=result.download;linkNode.hidden=false;
      }
      if(result.transcript&&textNode){
        textNode.value=result.transcript.text || "";
        for(const kind of ["srt","vtt"]){
          const link=$("#subtitle"+(kind==="srt"?"Srt":"Vtt"));
          link.href="/api/transcriptions/"+encodeURIComponent(id)+"/"+kind;
          link.hidden=false;
        }
      }
      return result;
    }
    statusNode.textContent=result.status==="running"?text("تتم المعالجة الآن...","Processing..."):text("في قائمة الانتظار","Queued...");
    await sleep(1800);
  }
  throw Error("Job polling timed out");
}
function setBusy(form,busy){const button=form.querySelector('button[type="submit"]');if(button)button.disabled=busy;}
async function runJob(ev,path,prefix,transcription=false){
  ev.preventDefault();const form=ev.currentTarget;
  const status=$("#"+prefix+"Status");
  const audio=transcription ? null : $("#"+prefix+"Audio"+(prefix==="enhance"?"Result":""));
  const link=transcription ? null : $("#"+prefix+"Download");
  setBusy(form,true);
  status.textContent=text("جاري الإرسال...","Uploading...");
  if(transcription){$("#subtitleSrt").hidden=true;$("#subtitleVtt").hidden=true;}
  if(audio)audio.hidden=true;
  if(link)link.hidden=true;
  try{
    const response=await api(path,{method:"POST",body:new FormData(form)});
    await watchJob(response.id,status,audio,link,transcription?$("#transcriptResult"):null);
  }catch(error){status.textContent=text("تعذّر التنفيذ: ","Failed: ")+fmtError(error);}
  finally{setBusy(form,false);}
}
async function refreshVoices(){
  try{voices=(await api("/api/voices")).voices;}
  catch(error){$("#voiceStatus").textContent=fmtError(error);return;}
  const box=$("#voiceList");box.textContent="";
  if(!voices.length)box.textContent=text("لا توجد تسجيلات محفوظة بعد.","No saved voice references.");
  voices.forEach((item)=>{
    const card=document.createElement("div");card.className="voice-item";
    const header=document.createElement("header");
    const name=document.createElement("strong");name.textContent=item.name;
    const remove=document.createElement("button");remove.type="button";remove.textContent=text("حذف","Delete");
    remove.addEventListener("click",async()=>{
      if(!confirm(text("هل تريدين حذف التسجيل المرجعي؟","Delete this reference recording?")))return;
      try{await api("/api/voices/"+encodeURIComponent(item.id),{method:"DELETE"});await refreshVoices();}
      catch(error){$("#voiceStatus").textContent=fmtError(error);}
    });
    header.append(name,remove);
    const audio=document.createElement("audio");audio.controls=true;
    audio.preload="none";audio.src="/api/voices/"+encodeURIComponent(item.id)+"/audio";
    card.append(header,audio);box.append(card);
  });
  ["dubVoice","providerVoice"].forEach((name)=>{
    const select=$("#"+name);select.textContent="";
    const blank=document.createElement("option");blank.value="";blank.textContent="Default";
    select.append(blank);
    voices.forEach(item=>{const opt=document.createElement("option");opt.value=item.id;opt.textContent=item.name;select.append(opt);});
  });
}
async function refreshTools(){
  try{toolStates=(await api("/api/tools")).tools;}
  catch(error){$("#toolList").textContent=fmtError(error);return;}
  const box=$("#toolList");box.textContent="";
  toolStates.forEach(item=>{
    const card=document.createElement("div");card.className="card mini-state";
    const title=document.createElement("strong");title.textContent=item.label;
    const detail=document.createElement("small");detail.textContent=item.detail;
    const state=document.createElement("em");state.textContent=item.ready?text("مهيأ (قد يحتاج اختبارًا واقعيًا)","Configured / pending real test"):text("غير مهيأ / غير متاح","Not configured / unavailable");
    card.append(title,detail,state);box.append(card);
  });
}
$("#voiceForm").addEventListener("submit",async(ev)=>{
  ev.preventDefault();const form=ev.currentTarget;setBusy(form,true);
  try{await api("/api/voices",{method:"POST",body:new FormData(form)});form.reset();$("#voiceStatus").textContent=text("حُفظ الصوت على الجهاز.","Voice saved locally.");await refreshVoices();}
  catch(error){$("#voiceStatus").textContent=fmtError(error);}
  finally{setBusy(form,false);}
});
$("#enhanceForm").addEventListener("submit",ev=>runJob(ev,"/api/enhance","enhance"));
$("#transcribeForm").addEventListener("submit",ev=>runJob(ev,"/api/transcribe","transcribe",true));
$("#dubForm").addEventListener("submit",ev=>runJob(ev,"/api/voiceover","dub"));
$("#providerForm").addEventListener("submit",ev=>runJob(ev,"/api/provider/speech","provider"));
$("#trainingForm").addEventListener("submit",ev=>runJob(ev,"/api/train","train"));
$("#qualityForm").addEventListener("submit",async(ev)=>{
  ev.preventDefault();const target=$("#qualityResult");target.textContent=text("جارٍ التحليل...","Analyzing...");
  try{const json=await api("/api/analyze",{method:"POST",body:new FormData(ev.currentTarget)});target.textContent=JSON.stringify(json,null,2);}
  catch(error){target.textContent=fmtError(error);}
});
$("#copyTranscript").addEventListener("click",async()=>{
  try{await navigator.clipboard.writeText($("#transcriptResult").value);}
  catch(error){$("#transcribeStatus").textContent=fmtError(error);}
});
async function recordMic(){
  const status=$("#micStatus"),button=$("#micCapture");
  if(!navigator.mediaDevices?.getUserMedia){status.textContent=text("المتصفح لا يدعم التسجيل الآمن.","Microphone recording unavailable.");return;}
  let stream,context,source,processor;
  button.disabled=true;
  try{
    stream=await navigator.mediaDevices.getUserMedia({audio:{channelCount:1,echoCancellation:true},video:false});
    context=new (window.AudioContext || window.webkitAudioContext)();
    source=context.createMediaStreamSource(stream);
    processor=context.createScriptProcessor(4096,1,1);
    const chunks=[];
    processor.onaudioprocess=(event)=>{
      chunks.push(new Float32Array(event.inputBuffer.getChannelData(0)));
      event.outputBuffer.getChannelData(0).fill(0);
    };
    source.connect(processor);processor.connect(context.destination);
    status.textContent=text("نسجل خمس ثوانٍ...","Recording five seconds...");
    await sleep(5000);
    processor.disconnect();source.disconnect();
    const count=chunks.reduce((sum,a)=>sum+a.length,0);
    if(count<128)throw Error("Microphone returned no audio samples.");
    const bytes=new ArrayBuffer(44+count*2),view=new DataView(bytes);
    const ascii=(offset,string)=>{for(let i=0;i<string.length;i++)view.setUint8(offset+i,string.charCodeAt(i));};
    const rate=context.sampleRate;
    ascii(0,"RIFF");view.setUint32(4,36+count*2,true);ascii(8,"WAVE");ascii(12,"fmt ");
    view.setUint32(16,16,true);view.setUint16(20,1,true);view.setUint16(22,1,true);
    view.setUint32(24,rate,true);view.setUint32(28,rate*2,true);
    view.setUint16(32,2,true);view.setUint16(34,16,true);ascii(36,"data");view.setUint32(40,count*2,true);
    let index=44;
    for(const samples of chunks)for(const sample of samples){
      const clamped=Math.max(-1,Math.min(1,sample));
      view.setInt16(index,clamped<0?clamped*32768:clamped*32767,true);index+=2;
    }
    const file=new File([bytes],"microphone-clip.wav",{type:"audio/wav"});
    const transfer=new DataTransfer();transfer.items.add(file);
    $("#audio").files=transfer.files;
    status.textContent=text("تم تسجيل مقطع WAV. اختاري نموذج Applio ثم اضغطي تحويل.","Recorded WAV clip. Select an Applio model and convert.");
  }catch(error){status.textContent=fmtError(error);}
  finally{if(processor)processor.disconnect();if(source)source.disconnect();if(stream)stream.getTracks().forEach(track=>track.stop());if(context)await context.close();button.disabled=false;}
}
$("#micCapture").addEventListener("click",recordMic);
refreshVoices();refreshTools();
})();
