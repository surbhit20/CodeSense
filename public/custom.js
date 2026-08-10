(function () {
  let graphPanel = null;
  let graphIframe = null;
  let toggleBtn = null;
  let pendingData = null;
  let minimized = false;

  var PANEL_WIDTH = '45vw';
  var MIN_PANEL_WIDTH = 280; // px
  var MAX_PANEL_WIDTH_RATIO = 0.85; // fraction of viewport width

  // The composer has no per-state placeholder support server-side (it's a
  // static translation string), so swap it here instead: an "explore a
  // codebase" prompt before anything's loaded, back to a generic one once
  // a repo's graph exists. #chat-input isn't mounted yet when this script
  // first runs, so wait for it rather than querying once and giving up.
  var LANDING_PLACEHOLDER = 'Explore this codebase: paste a GitHub link';
  var LOADED_PLACEHOLDER = 'Ask a question about this repo…';

  function setComposerPlaceholder(text) {
    var el = document.getElementById('chat-input');
    if (el) el.setAttribute('placeholder', text);
  }

  function whenComposerReady(cb) {
    var el = document.getElementById('chat-input');
    if (el) {
      cb(el);
      return;
    }
    var observer = new MutationObserver(function () {
      var el = document.getElementById('chat-input');
      if (el) {
        observer.disconnect();
        cb(el);
      }
    });
    observer.observe(document.body, { childList: true, subtree: true });
  }

  whenComposerReady(function () {
    setComposerPlaceholder(LANDING_PLACEHOLDER);
  });

  function sendToIframe(data) {
    if (graphIframe && graphIframe.contentWindow) {
      graphIframe.contentWindow.postMessage(data, '*');
    }
  }

  function setMinimized(state) {
    minimized = state;
    var appRoot = document.getElementById('root');
    if (minimized) {
      graphPanel.style.transform = 'translateX(100%)';
      toggleBtn.style.right = '0';
      toggleBtn.title = 'Show graph';
      if (appRoot) appRoot.style.marginRight = '0';
    } else {
      graphPanel.style.transform = 'translateX(0)';
      toggleBtn.style.right = PANEL_WIDTH;
      toggleBtn.title = 'Hide graph';
      if (appRoot) appRoot.style.marginRight = PANEL_WIDTH;
    }
  }

  // Applies a new panel width (from a drag) everywhere it's referenced.
  // Only takes effect visually while the panel isn't minimized — dragging
  // the handle only makes sense once the panel is actually showing, and
  // setMinimized() re-reads PANEL_WIDTH itself when restoring.
  function setPanelWidth(px) {
    PANEL_WIDTH = px + 'px';
    if (!graphPanel) return;
    graphPanel.style.width = PANEL_WIDTH;
    if (!minimized) {
      toggleBtn.style.right = PANEL_WIDTH;
      var appRoot = document.getElementById('root');
      if (appRoot) appRoot.style.marginRight = PANEL_WIDTH;
    }
  }

  // Drag-to-resize on the same handle that also toggles minimize on a
  // plain click — a mousedown+move past a small threshold commits to a
  // resize (and suppresses the click's toggle), anything smaller is just
  // a click.
  function initResize(handle) {
    var dragging = false;
    var moved = false;
    var startX = 0;
    var DRAG_THRESHOLD = 4; // px

    handle.addEventListener('mousedown', function (e) {
      if (minimized) return; // nothing to resize while hidden
      dragging = true;
      moved = false;
      startX = e.clientX;
      // Transitions fight a live drag (each intermediate width tries to
      // animate toward the next), and there's no reason to smooth-scroll
      // toward a position that's about to be immediately overridden by
      // the next mousemove anyway.
      graphPanel.style.transition = 'none';
      toggleBtn.style.transition = 'none';
      var appRoot = document.getElementById('root');
      if (appRoot) appRoot.style.transition = 'none';
      document.body.style.cursor = 'ew-resize';
      document.body.style.userSelect = 'none';
      // Shrinking the panel drags the cursor right, over the iframe's own
      // document — without this, mousemove targets flip to the iframe the
      // instant the cursor crosses into it, and this (parent) document
      // stops receiving them entirely, stalling the drag.
      if (graphIframe) graphIframe.style.pointerEvents = 'none';
      e.preventDefault();
    });

    window.addEventListener('mousemove', function (e) {
      if (!dragging) return;
      if (Math.abs(e.clientX - startX) > DRAG_THRESHOLD) moved = true;
      var raw = window.innerWidth - e.clientX;
      var min = MIN_PANEL_WIDTH;
      var max = window.innerWidth * MAX_PANEL_WIDTH_RATIO;
      setPanelWidth(Math.min(Math.max(raw, min), max));
    });

    window.addEventListener('mouseup', function () {
      if (!dragging) return;
      dragging = false;
      graphPanel.style.transition = 'transform 0.2s ease';
      toggleBtn.style.transition = 'right 0.2s ease';
      var appRoot = document.getElementById('root');
      if (appRoot) appRoot.style.transition = 'margin-right 0.2s ease';
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
      if (graphIframe) graphIframe.style.pointerEvents = '';
      // A real drag shouldn't also fire the click-to-minimize handler —
      // capture-phase click listener below eats exactly one click when
      // this is true.
      if (moved) suppressNextClick = true;
    });
  }

  var suppressNextClick = false;

  function createPanel() {
    if (graphPanel) return;

    // Narrow drag-handle strip pinned to the panel's left edge, sitting on
    // top of the 1px divider line. Visual styling (the grip affordance,
    // hover/focus states) lives in custom.css — this only sets layout.
    toggleBtn = document.createElement('button');
    toggleBtn.className = 'codesense-graph-toggle';
    toggleBtn.title = 'Hide graph';
    toggleBtn.style.cssText = [
      'position:fixed',
      'top:50%',
      'right:' + PANEL_WIDTH,
      'transform:translateY(-50%)',
      'width:14px',
      'height:56px',
      'z-index:1001',
      'padding:0',
      'transition:right 0.2s ease',
    ].join(';');
    toggleBtn.addEventListener('click', function (e) {
      if (suppressNextClick) {
        suppressNextClick = false;
        e.preventDefault();
        e.stopPropagation();
        return;
      }
      setMinimized(!minimized);
    });
    initResize(toggleBtn);

    var grip = document.createElement('span');
    grip.className = 'codesense-graph-toggle-grip';
    grip.setAttribute('aria-hidden', 'true');
    toggleBtn.appendChild(grip);

    document.body.appendChild(toggleBtn);

    // Graph panel — starts translated off-screen so its first appearance
    // slides in from the right instead of just popping into place.
    graphPanel = document.createElement('div');
    graphPanel.id = 'codesense-graph-panel';
    graphPanel.style.cssText = [
      'position:fixed',
      'top:60px',
      'right:0',
      'width:' + PANEL_WIDTH,
      'height:calc(100vh - 60px)',
      'z-index:999',
      'border-left:1px solid #333',
      'background:#1a1a1a',
      'transition:transform 0.2s ease',
      'transform:translateX(100%)',
    ].join(';');

    graphIframe = document.createElement('iframe');
    graphIframe.src = '/public/graph.html';
    // outline:none — clicking a node inside the iframe shifts DOM focus to
    // the <iframe> element itself in this (parent) document, and Chrome's
    // default focus ring then outlines the whole panel, not just the node
    // that was actually clicked.
    graphIframe.style.cssText = 'width:100%;height:100%;border:none;display:block;outline:none;';

    graphIframe.addEventListener('load', function () {
      if (pendingData) {
        sendToIframe(pendingData);
        pendingData = null;
      }
    });

    graphPanel.appendChild(graphIframe);
    document.body.appendChild(graphPanel);

    // Shrink Chainlit's app root so its own centered layout re-flows into
    // the space left of the panel, instead of the panel just overlaying
    // (and clipping) content that doesn't know it exists.
    var appRoot = document.getElementById('root');
    if (appRoot) {
      appRoot.style.transition = 'margin-right 0.2s ease';
    }

    // Force layout so the off-screen transform above is committed before
    // switching to the open position — otherwise the browser collapses
    // both states into one and nothing appears to animate.
    void graphPanel.offsetWidth;

    graphPanel.style.transform = 'translateX(0)';
    if (appRoot) appRoot.style.marginRight = PANEL_WIDTH;
  }

  window.addEventListener('message', function (e) {
    if (e.data && e.data.type === 'initGraph') {
      setComposerPlaceholder(LOADED_PLACEHOLDER);
      if (!graphPanel) {
        pendingData = e.data;
        createPanel();
      } else {
        sendToIframe(e.data);
      }
      return;
    }

    if (e.data && e.data.type === 'setBusy') {
      sendToIframe(e.data);
      return;
    }

    // nodeClick from the iframe is forwarded to Python directly by Chainlit's
    // own window.message listener — no re-dispatch needed here.
  });
})();
