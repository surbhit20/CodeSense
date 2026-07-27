(function () {
  let graphPanel = null;
  let graphIframe = null;
  let toggleBtn = null;
  let pendingData = null;
  let minimized = false;

  var PANEL_WIDTH = '45vw';

  function sendToIframe(data) {
    if (graphIframe && graphIframe.contentWindow) {
      graphIframe.contentWindow.postMessage(data, '*');
    }
  }

  function setMinimized(state) {
    minimized = state;
    if (minimized) {
      graphPanel.style.transform = 'translateX(100%)';
      toggleBtn.style.right = '0';
      toggleBtn.title = 'Show graph';
      toggleBtn.innerHTML = '&#9664;'; // ◀
    } else {
      graphPanel.style.transform = 'translateX(0)';
      toggleBtn.style.right = PANEL_WIDTH;
      toggleBtn.title = 'Hide graph';
      toggleBtn.innerHTML = '&#9654;'; // ▶
    }
  }

  function createPanel() {
    if (graphPanel) return;

    // Narrow vertical tab button pinned to the left edge of the panel.
    // border-right:none makes it look flush against the panel.
    toggleBtn = document.createElement('button');
    toggleBtn.innerHTML = '&#9654;'; // ▶
    toggleBtn.title = 'Hide graph';
    toggleBtn.style.cssText = [
      'position:fixed',
      'top:50%',
      'right:' + PANEL_WIDTH,
      'transform:translateY(-50%)',
      'width:18px',
      'height:64px',
      'z-index:1001',
      'background:#2d2d2d',
      'color:#aaa',
      'border:1px solid #555',
      'border-right:none',
      'border-radius:4px 0 0 4px',
      'cursor:pointer',
      'font-size:10px',
      'padding:0',
      'transition:right 0.2s ease',
      'display:flex',
      'align-items:center',
      'justify-content:center',
    ].join(';');
    toggleBtn.addEventListener('click', function () {
      setMinimized(!minimized);
    });
    document.body.appendChild(toggleBtn);

    // Graph panel
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
    ].join(';');

    graphIframe = document.createElement('iframe');
    graphIframe.src = '/public/graph.html';
    graphIframe.style.cssText = 'width:100%;height:100%;border:none;display:block;';

    graphIframe.addEventListener('load', function () {
      if (pendingData) {
        sendToIframe(pendingData);
        pendingData = null;
      }
    });

    graphPanel.appendChild(graphIframe);
    document.body.appendChild(graphPanel);
  }

  window.addEventListener('message', function (e) {
    if (e.data && e.data.type === 'initGraph') {
      if (!graphPanel) {
        pendingData = e.data;
        createPanel();
      } else {
        sendToIframe(e.data);
      }
      return;
    }

    // nodeClick from the iframe is forwarded to Python directly by Chainlit's
    // own window.message listener — no re-dispatch needed here.
  });
})();
