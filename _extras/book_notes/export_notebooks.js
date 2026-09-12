/* Run as a bookmarklet on read.amazon.com/notebook. No third-party requests. */
(async () => {
  "use strict";
  if (location.hostname !== "read.amazon.com" || location.pathname !== "/notebook") {
    alert("Open https://read.amazon.com/notebook and sign in first.");
    return;
  }
  if (document.getElementById("book-notes-export-progress")) return;
  const panel = document.createElement("div");
  panel.id = "book-notes-export-progress";
  Object.assign(panel.style, {position:"fixed",right:"16px",top:"16px",zIndex:"2147483647",
    background:"#fff",color:"#111",padding:"16px",border:"2px solid #222",maxWidth:"420px",
    font:"15px/1.5 system-ui",boxShadow:"0 4px 24px #0003"});
  const status = document.createElement("div");
  const stop = document.createElement("button");
  stop.textContent = "Stop and save progress";
  panel.append(status, stop);
  document.body.append(panel);
  let cancelled = false;
  stop.onclick = () => { cancelled = true; };
  const pause = ms => new Promise(resolve => setTimeout(resolve, ms));
  const wait = async (predicate, label) => {
    for (let n = 0; n < 150; n++) {
      if (cancelled) throw new Error("Stopped by user");
      if (predicate()) return;
      await pause(100);
    }
    throw new Error(`Timed out: ${label}`);
  };
  const text = node => node?.textContent?.replace(/\s+/g, " ").trim() || "";
  const lastCursor = (root, selector) => [...root.querySelectorAll(selector)].at(-1)?.value || "";
  const output = {version:1,source:"https://read.amazon.com/notebook",
    exported_at:new Date().toISOString(),complete:false,books:[],errors:[]};
  try {
    status.textContent = "Loading your annotated books. Keep this tab open while the export runs.";
    const search = document.getElementById("kp-notebook-search-input");
    if (search?.value) {
      search.value = "";
      search.dispatchEvent(new Event("input", {bubbles:true}));
      search.dispatchEvent(new Event("keyup", {bubbles:true}));
    }
    const library = document.getElementById("library");
    if (!library) throw new Error("Kindle library not found. Check that you are signed in.");
    const list = library.querySelector(".a-scroller");
    while (lastCursor(library, ".kp-notebook-library-next-page-start")) {
      const before = library.querySelectorAll(".kp-notebook-library-each-book").length;
      const cursor = lastCursor(library, ".kp-notebook-library-next-page-start");
      if (!list) throw new Error("Library scrolling area not found");
      list.scrollTop = list.scrollHeight;
      list.dispatchEvent(new Event("scroll", {bubbles:true}));
      await wait(() => library.querySelectorAll(".kp-notebook-library-each-book").length > before ||
        lastCursor(library, ".kp-notebook-library-next-page-start") !== cursor, "loading more books");
    }
    const books = [...library.querySelectorAll(".kp-notebook-library-each-book")]
      .map(node => ({asin:node.id,title:text(node.querySelector("h2")),
        cover_url:node.querySelector("img.kp-notebook-cover-image")?.src || null,
        author:text(node.querySelector("p")).replace(/^By:\s*/i, "")}));
    output.expected_books = books.length;
    if (!books.length) throw new Error("No annotated books found");
    for (const [i, book] of books.entries()) {
      if (cancelled) throw new Error("Stopped by user");
      status.textContent = `Exporting ${i + 1} of ${books.length}: ${book.title}`;
      try {
        const node = document.getElementById(book.asin);
        const link = node?.querySelector("a");
        if (!link) throw new Error("Book link no longer available");
        link.click();
        await wait(() => document.getElementById("kp-notebook-annotations-asin")?.value === book.asin &&
          document.getElementById("kp-notebook-annotations"), "opening book");
        let annotations = document.getElementById("kp-notebook-annotations");
        while (lastCursor(annotations, ".kp-notebook-annotations-next-page-start")) {
          const cursor = lastCursor(annotations, ".kp-notebook-annotations-next-page-start");
          const scroller = document.getElementById("annotation-scroller");
          if (!scroller) throw new Error("Highlight scrolling area not found");
          scroller.scrollTop = scroller.scrollHeight;
          scroller.dispatchEvent(new Event("scroll", {bubbles:true}));
          await wait(() => lastCursor(document.getElementById("kp-notebook-annotations"),
            ".kp-notebook-annotations-next-page-start") !== cursor, "loading more highlights");
          annotations = document.getElementById("kp-notebook-annotations");
        }
        const highlights = [];
        let unavailable = 0;
        for (const row of annotations.children) {
          const header = row.querySelector('[id="annotationHighlightHeader"]');
          if (!header) continue;
          const value = text(row.querySelector('[id="highlight"]'));
          if (value) highlights.push({text:value,reference:text(header)});
          else unavailable++;
        }
        // Read only the count label. The container's textContent concatenates
        // the access year with this count (e.g. 2024 + 32 becomes 202432).
        const reported = text(document.getElementById("kp-notebook-annotation-count"))
          .match(/^([\d,]+)\s+Highlights?\s*\|/i);
        const expected = reported ? Number(reported[1].replaceAll(",", "")) : null;
        // Capture the access date separately from highlight counts and passages.
        const accessLabel = [...document.getElementById("annotation-scroller").querySelectorAll("span")]
          .map(text).find(value => /^Last accessed on\s*/i.test(value));
        const lastAccessed = accessLabel?.match(/^Last accessed on\s*((?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),\s+[A-Za-z]+\s+\d{1,2},\s+\d{4})$/i)?.[1] || null;
        output.books.push({...book,highlights,unavailable_highlights:unavailable,
          expected_highlights:expected,last_accessed:lastAccessed});
        if (expected !== null && highlights.length + unavailable !== expected) {
          output.errors.push({title:book.title,asin:book.asin,
            error:`Amazon reports ${expected} highlights; captured ${highlights.length} text and ${unavailable} unavailable entries`});
        }
        await pause(300);
      } catch (error) {
        output.errors.push({title:book.title,asin:book.asin,error:String(error.message)});
        if (cancelled) throw error;
      }
    }
    output.complete = output.errors.length === 0;
  } catch (error) {
    output.errors.push({error:String(error.message)});
  }
  const blob = new Blob([JSON.stringify(output, null, 2) + "\n"], {type:"application/json"});
  const url = URL.createObjectURL(blob);
  const download = document.createElement("a");
  download.href = url;
  download.download = `kindle-notebooks-${new Date().toISOString().slice(0,10)}.json`;
  download.textContent = "Download highlights JSON";
  panel.append(download);
  download.click();
  status.textContent = `${output.complete ? "Finished" : "Partial export"}: ${output.books.length} books, ` +
    `${output.books.reduce((sum, b) => sum + b.highlights.length, 0)} text highlights, ` +
    `${output.errors.length} errors. The file includes any unavailable-content counts.`;
  stop.textContent = "Close";
  stop.onclick = () => { URL.revokeObjectURL(url); panel.remove(); };
})();
