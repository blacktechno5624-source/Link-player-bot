(() => {
  const video = document.getElementById("video");
  const status = document.getElementById("status");
  const url = video.dataset.url;
  const kind = video.dataset.kind;
  const fail = (message) => { status.textContent = message; status.className = "error"; };
  video.addEventListener("loadedmetadata", () => {
    status.textContent = "Metadata loaded. Press play to start.";
    status.className = "success";
  });
  video.addEventListener("error", () => {
    fail("Playback failed. The source may be expired, blocked, unsupported, or missing required CORS headers.");
  });
  if (kind === "hls") {
    if (video.canPlayType("application/vnd.apple.mpegurl")) {
      video.src = url;
    } else if (window.Hls && Hls.isSupported()) {
      const hls = new Hls();
      hls.loadSource(url);
      hls.attachMedia(video);
      hls.on(Hls.Events.ERROR, (_event, data) => {
        if (data.fatal) fail("HLS playback error. Check link validity and source CORS/access rules.");
      });
    } else {
      fail("This browser does not support HLS playback.");
    }
  } else {
    video.src = url;
  }
  video.load();
})();
