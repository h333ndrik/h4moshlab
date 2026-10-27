'use strict';
(() => {
  const media = matchMedia('(hover:hover) and (pointer:fine)');
  const cursor = document.createElement('div');
  cursor.className = 'h4-cursor';
  cursor.hidden = true;
  cursor.setAttribute('aria-hidden', 'true');
  const image = document.createElement('img');
  image.src = '/h4-cursor.svg'; image.alt = ''; image.draggable = false;
  cursor.append(image);
  let loaded = false, position = null;
  const hide = () => {
    cursor.hidden = true;
    document.documentElement.classList.remove('h4-cursor-ready');
  };
  function update() {
    if (!media.matches || !loaded || !position || document.hidden) return hide();
    const target = document.elementFromPoint(position.x, position.y);
    // Native video controls live in browser shadow DOM: retain the native cursor.
    if (!target || target.closest('video,iframe')) return hide();
    const dialog = target.closest('dialog[open]');
    const parent = dialog || document.body;
    if (cursor.parentElement !== parent) parent.append(cursor);
    const control = target.closest('button,a[href],input:not([type=hidden]),select,textarea,label,summary,[role=button],[role=link],[draggable=true]');
    const enabled = control && !control.matches(':disabled,[aria-disabled=true]') &&
      !control.closest('[inert],[aria-disabled=true]') &&
      !(control.tagName === 'LABEL' && (control.control || control.querySelector('input'))?.disabled);
    cursor.classList.toggle('is-clickable', Boolean(enabled));
    cursor.style.transform = `translate3d(${position.x - 7}px,${position.y - 2}px,0)`;
    cursor.hidden = false;
    document.documentElement.classList.add('h4-cursor-ready');
  }
  image.addEventListener('load', () => { loaded = true; update(); });
  image.addEventListener('error', () => { loaded = false; hide(); });
  document.body.append(cursor);
  document.addEventListener('pointermove', event => {
    if (event.pointerType !== 'mouse') return hide();
    position = {x:event.clientX, y:event.clientY}; update();
  }, {passive:true});
  document.addEventListener('pointerout', event => { if (!event.relatedTarget) { position = null; hide(); } });
  document.addEventListener('pointerdown', event => { if (event.pointerType !== 'mouse') hide(); }, {passive:true});
  document.addEventListener('dragstart', () => { position = null; hide(); });
  document.addEventListener('scroll', update, {capture:true, passive:true});
  window.addEventListener('blur', () => { position = null; hide(); });
  document.addEventListener('visibilitychange', () => { if (document.hidden) { position = null; hide(); } });
  media.addEventListener('change', () => { position = null; hide(); });
  new MutationObserver(update).observe(document.body, {subtree:true, attributes:true, attributeFilter:['disabled','aria-disabled','open','inert']});
})();
