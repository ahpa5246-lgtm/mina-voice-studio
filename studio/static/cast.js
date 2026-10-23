/* Cartoon casting studio. No fake voices: all lines call the real Chatterbox worker. */
(() => {
  "use strict";
  const $ = q => document.querySelector(q);
  const say = (ar, en) => document.documentElement.lang === "en" ? en : ar;
  let profiles = [], availableVoices = [];
  let lastCompletedEpisode = null;
  let selectedProjectVersion = null;
  const lineHost = $("#episodeLines");
  const err = error => error instanceof Error ? error.message : String(error);
  const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
  async function request(url, options) {
    const response = await fetch(url, options);
    let result;
    try { result = await response.json(); } catch (_) { result = {}; }
    if (!response.ok) throw Error(typeof result.detail === "string" ? result.detail : "HTTP " + response.status);
    return result;
  }
  function option(value, label) {
    const node = document.createElement("option");
    node.value = value;
    node.textContent = label;
    return node;
  }
  function options(select, entries, emptyText, oldValue) {
    select.replaceChildren(option("", emptyText));
    for (const entry of entries) select.append(option(entry.value, entry.label));
    if (entries.some(entry => entry.value === oldValue)) select.value = oldValue;
  }
  function syncModel() {
    const model = $("#castModel").value;
    const englishOnly = model === "turbo" || model === "nano";
    const qwen = model.startsWith("qwen-");
    const allowedQwen = new Set(["en","zh","ja","ko","de","fr","ru","pt","es","it"]);
    const lang = $("#castLang");
    if (englishOnly || (qwen && !allowedQwen.has(lang.value))) lang.value = "en";
    for (const item of lang.options) item.disabled =
      englishOnly ? item.value !== "en" : qwen && !allowedQwen.has(item.value);
    $("#castVoice").required = englishOnly || model === "qwen-clone";
    $("#castSpeaker").disabled = model !== "qwen-custom";
    $("#castReferenceText").disabled = model !== "qwen-clone";
  }
  $("#castModel").addEventListener("change", syncModel);
  $("#castVoice").addEventListener("change", () => {
    const selected = availableVoices.find(v => v.id === $("#castVoice").value);
    if(selected?.origin === "qwen-design") $("#castReferenceText").value = selected.seed_text || "";
  });
  const mainLanguages = Array.from($("#language").options, el => ({value: el.value, label: el.textContent}));
  const castLang = $("#castLang");
  const current = castLang.value;
  castLang.replaceChildren();
  for (const lang of mainLanguages) castLang.append(option(lang.value, lang.label));
  castLang.value = current;
  syncModel();

  async function refreshVoices() {
    const data = await request("/api/voices");
    availableVoices = data.voices;
    const choice = $("#castVoice"), previous = choice.value;
    options(choice, availableVoices.map(v => ({value: v.id, label: v.name})),
      say("الصوت الافتراضي — ليس هوية جديدة", "Default voice — not a new identity"), previous);
  }
  function fillSpeaker(select) {
    const value = select.value;
    options(select, profiles.map(p => ({value: p.id, label: p.name})),
      say("اختاري الشخصية", "Choose character"), value);
    if (!select.value && profiles.length === 1) select.value = profiles[0].id;
  }
  async function refreshCharacters() {
    profiles = (await request("/api/cast/characters")).characters;
    const target = $("#castList");
    target.replaceChildren();
    if (!profiles.length) {
      target.textContent = say("لا توجد شخصيات؛ أضيفي شخصية أولًا.", "No characters yet. Create one first.");
    }
    profiles.forEach(profile => {
      const card = document.createElement("div"); card.className = "voice-item";
      const header = document.createElement("header");
      const name = document.createElement("strong"); name.textContent = profile.name;
      const remove = document.createElement("button"); remove.type = "button";
      remove.textContent = say("حذف", "Delete");
      remove.addEventListener("click", async () => {
        if (!confirm(say("حذف ملف الشخصية؟", "Delete this character profile?"))) return;
        try {
          await request("/api/cast/characters/" + encodeURIComponent(profile.id), {method:"DELETE"});
          await refreshCharacters();
        } catch (error) { $("#castStatus").textContent = err(error); }
      });
      const description = document.createElement("small");
      const ref = availableVoices.find(v => v.id === profile.voice_id);
      description.textContent = [profile.model, profile.language,
        ref ? ref.name : say("الصوت الافتراضي، غير مميز", "Default identity (not unique)")].join(" · ");
      header.append(name, remove);card.append(header, description);target.append(card);
    });
    lineHost.querySelectorAll(".cast-speaker").forEach(fillSpeaker);
  }
  function addLine() {
    if (lineHost.children.length >= 48) {
      $("#episodeStatus").textContent = say("الحد الأقصى 48 جملة.", "Maximum 48 dialogue lines.");
      return;
    }
    const node = document.createElement("div");node.className="cast-line";
    const label = document.createElement("span");label.className="cast-line-label";
    label.textContent = say("جملة حوار", "Dialogue line");
    const remove = document.createElement("button");remove.type="button";remove.className="outline";
    remove.textContent="×";remove.setAttribute("aria-label","Remove dialogue line");
    remove.addEventListener("click",() => {
      if (lineHost.children.length <= 1) return;
      node.remove();renumber();
    });
    const header = document.createElement("div");header.className="cast-line-header";
    const retry=document.createElement("button");
    retry.type="button";retry.className="outline cast-retry";
    retry.textContent=say("إعادة توليد الجملة", "Retry this line");
    retry.addEventListener("click",async()=>{
      if(!lastCompletedEpisode){
        $("#episodeStatus").textContent=say("ولّدي الحلقة أولًا.", "Render the episode first.");
        return;
      }
      if(!$("#episodeConsent").checked){
        $("#episodeStatus").textContent=say("أكدي الإذن باستعمال الصوت.", "Confirm permission to use the voice.");
        return;
      }
      retry.disabled=true;
      const body=new FormData();
      body.set("text",node.querySelector(".cast-text").value);
      body.set("delivery",node.querySelector(".cast-delivery").value);
      body.set("consent","true");
      const number=Array.from(lineHost.children).indexOf(node)+1;
      try{
        const result=await request(
          "/api/cast/episodes/"+encodeURIComponent(lastCompletedEpisode)+"/retry/"+number,
          {method:"POST",body});
        $("#episodeStatus").textContent=say("توليد جملة واحدة...", "Re-rendering one line...");
        await watchJob(result.id);
      }catch(error){$("#episodeStatus").textContent=err(error);}
      finally{retry.disabled=false;}
    });
    const tools=document.createElement("div");tools.className="cast-line-tools";
    tools.append(retry,remove);header.append(label,tools);
    const speaker = document.createElement("select");speaker.className="cast-speaker";
    speaker.required=true;
    fillSpeaker(speaker);
    const dialogue = document.createElement("textarea");
    dialogue.className="cast-text";dialogue.rows=2;dialogue.maxLength=500;
    dialogue.required=true;dialogue.dir="auto";
    dialogue.placeholder=say("اكتبي الحوار كما تريدين أن يُنطق...", "Write the dialogue as it should be spoken...");
    const actions = document.createElement("div");actions.className="cast-line-actions";
    const delivery = document.createElement("select");delivery.className="cast-delivery";
    for (const [key,ar,en] of [
      ["neutral","طبيعي","Neutral"],["energetic","حيوي","Energetic"],
      ["sarcastic","ساخر تقريبًا","Sarcastic approximation"],
      ["quiet","هادئ","Quiet"],["dramatic","درامي","Dramatic approximation"],
      ["angry","غاضب","Angry"],["sad","حزين","Sad"],["crying","يبكي","Crying"]
    ]) delivery.append(option(key,say(ar,en)));
    const pause = document.createElement("input");pause.className="cast-pause";
    pause.type="number";pause.min="0";pause.max="2000";pause.step="50";pause.value="250";
    pause.title=say("صمت بعد الجملة بالمللي ثانية","Pause after line in milliseconds");
    actions.append(speaker,delivery,pause);
    node.append(header,dialogue,actions);lineHost.append(node);
    renumber();
  }
  function renumber() {
    lineHost.querySelectorAll(".cast-line-label").forEach((label,i) => {
      label.textContent=say("جملة ","Line ")+(i+1);
    });
  }
  $("#qwenDesignForm").addEventListener("submit",async event => {
    event.preventDefault();
    const form = event.currentTarget, button=form.querySelector('[type="submit"]');
    button.disabled=true;
    const status=$("#qwenDesignStatus");
    const preview=$("#qwenDesignPreview");
    preview.hidden=true;
    status.textContent=say("إرسال طلب تصميم الصوت...", "Submitting voice design request...");
    try{
      const job=await request("/api/qwen/design",{method:"POST",body:new FormData(form)});
      let finished=false;
      for(let i=0;i<900;i++){
        const result=await request("/api/jobs/"+encodeURIComponent(job.id));
        if(result.status==="failed") throw Error(result.error||"Qwen design failed");
        if(result.status==="completed"){
          if(!result.voice?.id||!result.download)throw Error("No voice was saved.");
          preview.src=result.download;preview.hidden=false;
          status.textContent=say("صوت جديد محفوظ في المكتبة: ","New designed voice saved: ")+result.voice.name;
          await refreshVoices();
          $("#castModel").value="qwen-clone";syncModel();
          $("#castVoice").value=result.voice.id;
          $("#castVoice").dispatchEvent(new Event("change"));
          $("#castName").value=result.voice.name;
          finished=true;break;
        }
        status.textContent=say("يجري تصميم الهوية الصوتية...", "Generating voice identity...");
        await sleep(1700);
      }
      if(!finished)throw Error("Design job polling timed out");
    }catch(error){status.textContent=err(error);}
    finally{button.disabled=false;}
  });

  function collectDialogue() {
    const lines=[];let total=0;
    for(const node of lineHost.querySelectorAll(".cast-line")){
      const text=node.querySelector(".cast-text").value.trim();
      const character_id=node.querySelector(".cast-speaker").value;
      if(!text || !character_id)throw Error(say("كل جملة تحتاج شخصية ونصًا.", "Each line needs a character and text."));
      const pause_ms=Number(node.querySelector(".cast-pause").value);
      if(!Number.isInteger(pause_ms)||pause_ms<0||pause_ms>2000)throw Error("Invalid pause (0-2000ms)");
      total+=text.length;
      lines.push({character_id,text,delivery:node.querySelector(".cast-delivery").value,pause_ms});
    }
    if(!lines.length||lines.length>48||total>6000)throw Error("Episode limit: 48 lines / 6000 characters");
    return lines;
  }
  function clearEpisodePlayback() {
    lastCompletedEpisode=null;
    for(const id of ["episodePreview","episodeZip","episodeSrt","checkSpeaker","speakerReport"])$("#"+id).hidden=true;
  }
  async function refreshProjects(preferred=null) {
    const chosen=preferred===null?$("#episodeProjectSelect").value:preferred;
    const list=(await request("/api/cast/projects")).projects;
    options($("#episodeProjectSelect"),list.map(p=>({value:p.id,label:p.title+" · v"+p.version})),
      say("مشروع جديد", "New script"),chosen);
  }
  $("#loadEpisodeProject").addEventListener("click",async()=>{
    const id=$("#episodeProjectSelect").value;
    if(!id){
      $("#episodeProjectStatus").textContent=say("اختاري مشروعًا محفوظًا.", "Choose a saved project.");
      return;
    }
    try{
      const project=(await request("/api/cast/projects/"+encodeURIComponent(id))).project;
      await refreshCharacters();
      $("#episodeProjectTitle").value=project.title;
      selectedProjectVersion=project.version;
      lineHost.replaceChildren();
      for(const line of project.lines){
        addLine();const node=lineHost.lastElementChild;
        node.querySelector(".cast-speaker").value=line.character_id;
        node.querySelector(".cast-text").value=line.text;
        node.querySelector(".cast-delivery").value=line.delivery;
        node.querySelector(".cast-pause").value=String(line.pause_ms);
      }
      const missing=project.lines.some((line,i)=>
        lineHost.children[i].querySelector(".cast-speaker").value!==line.character_id);
      $("#episodeProjectStatus").textContent=missing
        ?say("بعض الشخصيات حُذفت؛ أعيدي تعيينها.", "Some characters were deleted; reassign them.")
        :say("تم فتح السيناريو.", "Saved script loaded.");
      clearEpisodePlayback();
    }catch(error){$("#episodeProjectStatus").textContent=err(error);}
  });
  $("#saveEpisodeProject").addEventListener("click",async()=>{
    const button=$("#saveEpisodeProject");button.disabled=true;
    try{
      const lines=collectDialogue(),title=$("#episodeProjectTitle").value.trim();
      const id=$("#episodeProjectSelect").value;
      const payload={title,lines,...(id?{expected_version:selectedProjectVersion}:{})};
      const result=await request(id?"/api/cast/projects/"+encodeURIComponent(id):"/api/cast/projects",
        {method:id?"PUT":"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)});
      selectedProjectVersion=result.project.version;
      await refreshProjects(result.project.id);
      $("#episodeProjectStatus").textContent=say("حُفظ الإصدار ", "Saved version ")+result.project.version;
    }catch(error){$("#episodeProjectStatus").textContent=err(error);}
    finally{button.disabled=false;}
  });
  $("#deleteEpisodeProject").addEventListener("click",async()=>{
    const id=$("#episodeProjectSelect").value;
    if(!id)return;
    if(!confirm(say("حذف السيناريو المحفوظ؟", "Delete this saved script?")))return;
    try{
      await request("/api/cast/projects/"+encodeURIComponent(id),{method:"DELETE"});
      selectedProjectVersion=null;await refreshProjects("");
      $("#episodeProjectStatus").textContent=say("حُذف السيناريو، وبقيت الأصوات.", "Deleted script; character voices are retained.");
    }catch(error){$("#episodeProjectStatus").textContent=err(error);}
  });
  $("#episodeProjectSelect").addEventListener("change",()=>{selectedProjectVersion=null;});

  $("#addCastLine").addEventListener("click",addLine);
  $("#castForm").addEventListener("submit",async event => {
    event.preventDefault();
    const form = event.currentTarget,button=form.querySelector('[type="submit"]');
    button.disabled=true;
    try {
      const data=await request("/api/cast/characters",{method:"POST",body:new FormData(form)});
      $("#castStatus").textContent=say("تم حفظ الشخصية: ","Character saved: ")+data.character.name;
      form.reset();syncModel();
      await refreshCharacters();
    } catch (error) { $("#castStatus").textContent=err(error); }
    finally { button.disabled=false; }
  });
  async function watchJob(id) {
    const status=$("#episodeStatus"),progress=$("#episodeProgress");
    for(let i=0;i<3600;i++){
      const result=await request("/api/jobs/"+encodeURIComponent(id));
      if(result.status==="failed")throw Error(result.error || "Cartoon voice rendering failed");
      if(result.status==="completed"){
        if(!result.archive || !result.captions || !result.download)
          throw Error("The episode did not produce all required audio files.");
        $("#episodeZip").href=result.archive;$("#episodeZip").hidden=false;
        $("#episodeSrt").href=result.captions;$("#episodeSrt").hidden=false;
        const player=$("#episodePreview");player.src=result.download;player.hidden=false;
        lastCompletedEpisode=id;
        $("#checkSpeaker").hidden=false;
        const seconds=result.episode?.duration_seconds;
        status.textContent=say("اكتمل التوليد الحقيقي للحلقة.","The episode is rendered with the installed speech model.");
        progress.textContent=seconds?say("مدة الحلقة: ","Episode duration: ")+seconds+"s":"";
        return;
      }
      progress.textContent=result.current_line
        ? say("الجملة ","Rendering line ")+result.current_line+" / "+result.total_lines
        : say("في طابور المعالجة","Queued for rendering");
      await sleep(1600);
    }
    throw Error("Rendering status check expired; inspect the server job.");
  }
  $("#episodeForm").addEventListener("submit",async event=>{
    event.preventDefault();const form=event.currentTarget,button=form.querySelector('[type="submit"]');
    const lines=[];
    let total=0;
    for(const node of lineHost.querySelectorAll(".cast-line")){
      const text=node.querySelector(".cast-text").value.trim();
      if(!text || !node.querySelector(".cast-speaker").value) {
        $("#episodeStatus").textContent=say("كل جملة تحتاج شخصية ونصًا.","Every line needs a character and text.");
        return;
      }
      total+=text.length;
      lines.push({character_id:node.querySelector(".cast-speaker").value,
        text,delivery:node.querySelector(".cast-delivery").value,
        pause_ms:Number(node.querySelector(".cast-pause").value)});
    }
    if(total>6000 || lines.length>48) {
      $("#episodeStatus").textContent=say("الحد 6000 حرف و48 جملة.","Maximum 6000 characters / 48 lines.");
      return;
    }
    button.disabled=true;
    $("#episodeZip").hidden=true;$("#episodeSrt").hidden=true;
    $("#episodePreview").hidden=true;
    $("#checkSpeaker").hidden=true;$("#speakerReport").hidden=true;
    lastCompletedEpisode=null;
    $("#episodeStatus").textContent=say("إرسال سيناريو الحلقة...","Submitting episode script...");
    try{
      const payload=new FormData();
      payload.set("script_json",JSON.stringify(lines));
      payload.set("consent",$("#episodeConsent").checked?"true":"false");
      const job=await request("/api/cast/episodes",{method:"POST",body:payload});
      await watchJob(job.id);
    }catch(error){$("#episodeStatus").textContent=say("فشل: ","Failed: ")+err(error);}
    finally{button.disabled=false;}
  });
  $("#checkSpeaker").addEventListener("click",async()=>{
    if(!lastCompletedEpisode)return;
    const button=$("#checkSpeaker"),box=$("#speakerReport");
    button.disabled=true;box.hidden=false;
    box.textContent=say("يتم تحميل نموذج بصمة المتحدث...", "Evaluating real speaker embeddings...");
    try{
      const submitted=await request(
        "/api/cast/episodes/"+encodeURIComponent(lastCompletedEpisode)+"/speaker-report",
        {method:"POST"});
      let complete=false;
      for(let i=0;i<500;i++){
        const progress=await request("/api/jobs/"+encodeURIComponent(submitted.id));
        if(progress.status==="failed")throw Error(progress.error||"Speaker evaluation failed");
        if(progress.status==="completed"){
          if(!progress.report)throw Error("No speaker similarity report returned");
          box.textContent=JSON.stringify(progress.report,null,2);
          complete=true;break;
        }
        await sleep(1600);
      }
      if(!complete)throw Error("Speaker evaluation polling limit reached");
    }catch(error){box.textContent=say("تعذر التقييم: ","Evaluation failed: ")+err(error);}
    finally{button.disabled=false;}
  });
  document.querySelector('.nav[data-tab="cast"]').addEventListener("click",async()=>{
    try{await refreshVoices();await refreshCharacters();await refreshProjects();}
    catch(error){$("#castStatus").textContent=err(error);}
  });
  addLine();
  Promise.resolve().then(refreshProjects).catch(error=>{$("#episodeProjectStatus").textContent=err(error);});
  Promise.resolve().then(refreshVoices).then(refreshCharacters).catch(error=>{
    $("#castStatus").textContent=err(error);
  });
})();
