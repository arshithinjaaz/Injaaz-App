/**
 * DocHub — document list, editor, uploads (API: /api/docs)
 */
(function () {
  /** JSON API calls; omit Authorization when no token so JWT can use cookies (JWT_TOKEN_LOCATION). */
  function jsonHeaders() {
    const headers = { 'Content-Type': 'application/json' };
    const t = localStorage.getItem('access_token');
    if (t) headers['Authorization'] = 'Bearer ' + t;
    return headers;
  }

  /**
   * Authenticated fetch: credentials + Bearer only when token exists; retry once after refresh on 401.
   * Do not set Content-Type for FormData (browser sets multipart boundary).
   */
  async function apiFetch(url, options = {}) {
    const isFormData =
      typeof FormData !== 'undefined' && options.body instanceof FormData;
    const buildHeaders = () => {
      const incoming = options.headers;
      const base =
        incoming && typeof incoming === 'object' && !(incoming instanceof Headers)
          ? { ...incoming }
          : {};
      const t = localStorage.getItem('access_token');
      if (t) base['Authorization'] = 'Bearer ' + t;
      else delete base['Authorization'];
      if (isFormData) {
        delete base['Content-Type'];
        delete base['content-type'];
      }
      return base;
    };
    const run = () =>
      fetch(url, { ...options, headers: buildHeaders(), credentials: 'include' });
    let r = await run();
    if (r.status !== 401 || !window.ApiClient) return r;
    const newTok = await window.ApiClient.refreshAccessToken();
    if (!newTok) return r;
    return run();
  }

  const CAT_META = {
    onboarding: { label: 'Onboarding', icon: '🚀' },
    contracts: { label: 'Project Contracts', icon: '📝' },
    policies: { label: 'Policies', icon: '📜' },
    manuals: { label: 'User Manuals', icon: '📖' },
    reports: { label: 'Reports', icon: '📊' },
    other: { label: 'Other', icon: '📄' },
    Internal: { label: 'Internal', icon: '📄' },
    API: { label: 'API', icon: '📄' },
    Guide: { label: 'Guide', icon: '📄' },
    Legal: { label: 'Legal', icon: '📄' },
    Spec: { label: 'Spec', icon: '📄' }
  };

  const TEMPLATES = {
    onboarding: `<h1>Employee Onboarding Guide</h1>
<div class="callout callout-blue"><span class="callout-icon">👋</span><div><strong>Welcome to the team!</strong> This guide will help you get up and running quickly.</div></div>
<h2>1. Company Overview</h2>
<p>We are a fast-growing company with a mission to deliver excellence.</p>
<h2>2. Your First Week</h2>
<ul>
  <li><strong>Day 1:</strong> Meet your team lead, set up workstation, complete HR paperwork</li>
  <li><strong>Day 2:</strong> System access provisioning, complete security training</li>
</ul>
<h2>3. Tools &amp; Access</h2>
<table class="dh-editor-table">
<thead><tr><th>Tool</th><th>Purpose</th><th>Access</th><th>Additional document</th></tr></thead>
<tbody>
<tr><td>Email</td><td>Communication</td><td>IT will provision</td><td class="dh-ref-cell"><span class="dh-ref-hint">Attach files under Additional documents at the bottom</span></td></tr>
<tr><td>DocHub</td><td>Document management</td><td>You are here</td><td class="dh-ref-cell"><span class="dh-ref-hint">—</span></td></tr>
</tbody>
</table>
<h2>4. Key Contacts</h2>
<ul><li><strong>HR:</strong> hr@example.com</li><li><strong>IT:</strong> it@example.com</li></ul>`,

    contracts: `<h1>Project Services Agreement</h1>
<p><em>This Agreement is entered into as of the date signed below.</em></p>
<h2>1. Parties</h2>
<p><strong>Service Provider:</strong> [Company Name].<br/><strong>Client:</strong> [Client Name].</p>
<h2>2. Scope of Services</h2>
<ul><li>Services as described in Schedule A</li></ul>`,

    policies: `<h1>Remote Work Policy</h1>
<div class="callout"><span class="callout-icon">⚠️</span><div>This policy is effective from <strong>January 1, 2025</strong>.</div></div>
<h2>1. Purpose</h2>
<p>This policy establishes clear guidelines for employees working remotely.</p>`,

    manuals: `<h1>DocHub User Manual</h1>
<p><em>Version 1.0</em></p>
<h2>1. Getting Started</h2>
<p>Welcome to DocHub — your organisation's central document management platform.</p>`,

    reports: `<h1>Performance Report</h1>
<p><em>Prepared by: Analytics Team</em></p>
<h2>1. Executive Summary</h2>
<p>Add summary here.</p>`,

    other: `<h1>Untitled Document</h1><p>Start writing your document here.</p>`
  };

  const LABELS = {
    all: 'All Document',
    published: 'Published',
    starred: 'Starred',
    recent: 'Recent',
    draft: 'Drafts',
    review: 'In review',
    uploads: 'File uploads',
    internal: 'Internal',
    analytics: 'Analytics',
    archived: 'Archived',
    onboarding: 'Onboarding',
    contracts: 'Project Contracts',
    policies: 'Policies',
    manuals: 'User Manuals',
    reports: 'Reports'
  };

  let docs = [];
  let dhIsAdmin = false;
  /** DocHub library access (view, list, star, export). */
  let dhCanWrite = false;
  /** Create/edit/upload/publish/delete/additional docs — administrators only. */
  let dhCanEdit = false;
  let me = null;

  let filterBucket = 'all';
  /** Sidebar buckets manually collapsed while filterBucket still matches (click row again to close). */
  let sbCollapsedBuckets = new Set();
  let searchQ = '';
  let currentDocId = null;
  let viewMode = 'view';
  let dirty = false;
  let currentEditorStatus = 'draft';
  let tocTimer = null;
  /** Blob URL for PDF iframe / image preview; revoked when switching documents. */
  let dhUploadPreviewUrl = null;

  function revokeUploadPreviewUrl() {
    if (dhUploadPreviewUrl) {
      URL.revokeObjectURL(dhUploadPreviewUrl);
      dhUploadPreviewUrl = null;
    }
  }

  const PDFJS_WORKER =
    'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js';

  function uploadPreviewKind(fileType) {
    const t = (fileType || '').toLowerCase();
    if (t === 'pdf') return 'pdf';
    if (t === 'md') return 'markdown';
    if (['png', 'jpg', 'jpeg', 'gif', 'webp'].includes(t)) return 'image';
    return 'none';
  }

  function fallbackPdfIframe(buf, vc, docName) {
    revokeUploadPreviewUrl();
    const pdfBlob = new Blob([buf], { type: 'application/pdf' });
    dhUploadPreviewUrl = URL.createObjectURL(pdfBlob);
    vc.innerHTML = '';
    const wrap = document.createElement('div');
    wrap.className = 'dh-file-preview-wrap';
    const iframe = document.createElement('iframe');
    iframe.className = 'dh-file-preview-frame';
    iframe.title = docName || 'PDF preview';
    iframe.src = dhUploadPreviewUrl;
    wrap.appendChild(iframe);
    vc.appendChild(wrap);
  }

  async function renderPdfWithPdfJs(buf, docId, vc, docName) {
    const pdfjsLib = typeof window !== 'undefined' ? window.pdfjsLib : null;
    if (!pdfjsLib || typeof pdfjsLib.getDocument !== 'function') {
      fallbackPdfIframe(buf, vc, docName);
      return;
    }
    try {
      pdfjsLib.GlobalWorkerOptions.workerSrc = PDFJS_WORKER;
      const loadingTask = pdfjsLib.getDocument({ data: buf });
      const pdf = await loadingTask.promise;
      if (currentDocId !== docId) return;
      vc.innerHTML = '';
      const scroll = document.createElement('div');
      scroll.className = 'dh-pdfjs-scroll';
      const pagesWrap = document.createElement('div');
      pagesWrap.className = 'dh-pdfjs-pages';
      for (let p = 1; p <= pdf.numPages; p++) {
        if (currentDocId !== docId) return;
        const page = await pdf.getPage(p);
        const viewport = page.getViewport({ scale: 1.35 });
        const canvas = document.createElement('canvas');
        const ctx = canvas.getContext('2d');
        if (!ctx) {
          throw new Error('Canvas unsupported');
        }
        canvas.width = viewport.width;
        canvas.height = viewport.height;
        const renderTask = page.render({ canvasContext: ctx, viewport });
        await renderTask.promise;
        const pageWrap = document.createElement('div');
        pageWrap.className = 'dh-pdfjs-page-wrap';
        pageWrap.appendChild(canvas);
        pagesWrap.appendChild(pageWrap);
      }
      scroll.appendChild(pagesWrap);
      vc.appendChild(scroll);
    } catch (err) {
      console.warn('DocHub PDF.js preview failed, using iframe fallback', err);
      fallbackPdfIframe(buf, vc, docName);
    }
  }

  function esc(s) {
    const d = document.createElement('div');
    d.textContent = s == null ? '' : String(s);
    return d.innerHTML;
  }

  function escAttr(s) {
    return String(s || '')
      .replace(/&/g, '&amp;')
      .replace(/"/g, '&quot;')
      .replace(/</g, '&lt;');
  }

  function stripHtml(html) {
    const d = document.createElement('div');
    d.innerHTML = html || '';
    return (d.textContent || '').trim();
  }

  function docRefs(doc) {
    if (!doc) return [];
    const r = doc.reference_attachments;
    return Array.isArray(r) ? r : [];
  }

  /** Same-origin download URL with suggested filename (server sends Content-Disposition: attachment). */
  function refAttachmentHref(baseUrl, filename) {
    const base = String(baseUrl || '');
    const fn = String(filename || 'download').split('/').pop() || 'download';
    const sep = base.indexOf('?') >= 0 ? '&' : '?';
    return base + sep + 'dn=' + encodeURIComponent(fn);
  }

  function fileExtFromName(name) {
    const n = String(name || '');
    const i = n.lastIndexOf('.');
    return i >= 0 ? n.slice(i + 1).toLowerCase() : '';
  }

  function kindLabelFromExt(ext) {
    const m = {
      pdf: 'PDF',
      docx: 'Word',
      doc: 'Word',
      xlsx: 'Excel',
      xls: 'Excel',
      pptx: 'PowerPoint',
      ppt: 'PowerPoint',
      md: 'Markdown',
      zip: 'ZIP'
    };
    return m[ext] || (ext ? ext.toUpperCase() : 'File');
  }

  function iconForFilename(name) {
    const ext = fileExtFromName(name);
    if (ext === 'pdf') return '📕';
    if (ext === 'docx' || ext === 'doc') return '📘';
    if (ext === 'xlsx' || ext === 'xls') return '📗';
    if (ext === 'pptx' || ext === 'ppt') return '📙';
    if (ext === 'zip') return '🗂️';
    if (ext === 'md') return '📝';
    return '📎';
  }

  /** Renders linked supporting files as a document list (not inline body content). */
  function buildAdditionalDocsHtml(refs, editable) {
    if (!refs.length) {
      return (
        '<div class="dh-add-doc-empty">' +
        '<p class="dh-add-doc-empty-title">No additional documents yet</p>' +
        '<p class="dh-add-doc-empty-hint">Attach PDFs, Word, Excel, or other files that belong with this page.</p>' +
        '</div>'
      );
    }
    const items = refs.map((item, idx) => {
      const name = esc(item.filename || 'Document');
      const href = refAttachmentHref(item.url, item.filename);
      const url = escAttr(href);
      const dl = escAttr(String(item.filename || 'download').split('/').pop());
      const ext = fileExtFromName(item.filename);
      const kind = esc(kindLabelFromExt(ext));
      const icon = esc(iconForFilename(item.filename));
      let row =
        '<li class="dh-add-doc-item">' +
        '<span class="dh-add-doc-icon" aria-hidden="true">' +
        icon +
        '</span>' +
        '<div class="dh-add-doc-main">' +
        '<a class="dh-add-doc-link" href="' +
        url +
        '" download="' +
        dl +
        '">' +
        name +
        '</a>' +
        '<span class="dh-add-doc-meta">Additional document · ' +
        kind +
        '</span>' +
        '</div>';
      if (editable) {
        row +=
          '<button type="button" class="dh-add-doc-remove" data-idx="' +
          idx +
          '" aria-label="Remove this document">×</button>';
      }
      row += '</li>';
      return row;
    });
    return '<ul class="dh-add-doc-list">' + items.join('') + '</ul>';
  }

  function renderRefDocsBar(doc) {
    const viewerFooter = document.getElementById('dhRefDocsFooterViewer');
    const editorFooter = document.getElementById('dhRefDocsFooterEditor');
    const addE = document.getElementById('dhFooterRefAddEditor');
    const chipsV = document.getElementById('dhRefDocsFooterChipsViewer');
    const chipsE = document.getElementById('dhRefDocsFooterChipsEditor');

    if (!doc || doc.doc_type !== 'content') {
      if (viewerFooter) viewerFooter.style.display = 'none';
      if (editorFooter) editorFooter.style.display = 'none';
      return;
    }

    const refs = docRefs(doc);
    const showEditControls = !!dhCanEdit && viewMode === 'edit';
    const html = buildAdditionalDocsHtml(refs, showEditControls);
    if (chipsV) chipsV.innerHTML = html;
    if (chipsE) chipsE.innerHTML = html;
    if (viewerFooter) viewerFooter.style.display = '';
    if (editorFooter) editorFooter.style.display = '';
    if (addE)
      addE.style.display = dhCanEdit && viewMode === 'edit' ? 'inline-flex' : 'none';
  }

  async function removeReferenceAt(idx) {
    if (!dhCanEdit) return;
    const doc = docs.find(d => d.id === currentDocId);
    if (!doc || doc.doc_type !== 'content') return;
    const refs = docRefs(doc);
    const item = refs[idx];
    if (!item) return;
    const fid = item.feed_document_id;
    const next = refs.filter((_, i) => i !== idx);
    const ok = await patchDoc(doc.id, { reference_attachments: next });
    if (!ok) return;
    if (fid != null) {
      await apiFetch('/api/docs/' + fid, { method: 'DELETE' });
    }
    await loadDocs(false);
    const fresh = docs.find(d => d.id === currentDocId);
    if (fresh) renderRefDocsBar(fresh);
    toast('Additional document removed');
  }

  function normalizeInlineRefUrl(u) {
    const s = String(u || '').trim();
    if (!s) return '';
    if (s.startsWith('http://') || s.startsWith('https://')) {
      try {
        const p = new URL(s).pathname;
        return p.startsWith('/api/docs/inline/') ? p : '';
      } catch (e) {
        return '';
      }
    }
    return s.startsWith('/api/docs/inline/') ? s : '';
  }

  async function addDocumentReferenceFiles(fileList) {
    const files = Array.from(fileList || []).filter(Boolean);
    if (!files.length) return;
    if (!dhCanEdit) {
      toast('Only administrators can attach additional documents', true);
      return;
    }
    const doc = docs.find(d => Number(d.id) === Number(currentDocId));
    if (!doc || doc.doc_type !== 'content') {
      toast('Open a text document to attach additional documents', true);
      return;
    }
    const refs = docRefs(doc).slice();
    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      const fd = new FormData();
      fd.append('file', file);
      if (doc.tag) fd.append('category', doc.tag);
      const r = await apiFetch('/api/docs/inline-reference', {
        method: 'POST',
        body: fd
      });
      const j = await r.json().catch(() => ({}));
      if (!r.ok || j.success === false) {
        toast(j.error || j.message || 'Upload failed', true);
        return;
      }
      const rawUrl = j.url || (j.data && j.data.url);
      const url = normalizeInlineRefUrl(rawUrl) || rawUrl;
      const fname = j.filename || (j.data && j.data.filename) || 'reference';
      const fidRaw = j.feed_document_id != null ? j.feed_document_id : j.data && j.data.feed_document_id;
      if (!url || !String(url).includes('/api/docs/inline/')) {
        toast('Upload failed — invalid file URL', true);
        return;
      }
      const entry = { url, filename: fname };
      if (fidRaw != null && !Number.isNaN(Number(fidRaw))) entry.feed_document_id = Number(fidRaw);
      refs.push(entry);
    }
    const idxLocal = docs.findIndex(d => Number(d.id) === Number(doc.id));
    if (idxLocal >= 0) {
      docs[idxLocal] = { ...docs[idxLocal], reference_attachments: refs };
      renderRefDocsBar(docs[idxLocal]);
    }
    const ok = await patchDoc(doc.id, { reference_attachments: refs });
    if (!ok) {
      await loadDocs(false);
      const rec = docs.find(d => Number(d.id) === Number(currentDocId));
      if (rec) renderRefDocsBar(rec);
      return;
    }
    await loadDocs(false);
    let fresh = docs.find(d => Number(d.id) === Number(currentDocId));
    if (
      fresh &&
      refs.length &&
      (!Array.isArray(fresh.reference_attachments) || fresh.reference_attachments.length === 0)
    ) {
      const idx = docs.findIndex(d => Number(d.id) === Number(doc.id));
      if (idx >= 0) {
        docs[idx] = { ...docs[idx], reference_attachments: refs };
        fresh = docs[idx];
      }
    }
    if (fresh) renderRefDocsBar(fresh);
    toast(files.length > 1 ? 'Additional documents attached' : 'Additional document attached');
  }

  function bindRefChipContainers() {
    ['dhRefDocsFooterChipsViewer', 'dhRefDocsFooterChipsEditor'].forEach(id => {
      const el = document.getElementById(id);
      if (!el || el._dhRefBound) return;
      el._dhRefBound = true;
      el.addEventListener('click', e => {
        const btn = e.target.closest('.dh-add-doc-remove');
        if (!btn) return;
        e.preventDefault();
        const idx = parseInt(btn.getAttribute('data-idx'), 10);
        if (!Number.isNaN(idx)) removeReferenceAt(idx);
      });
    });
  }

  function statusLabel(s) {
    if (s === 'review') return 'In Review';
    if (s === 'archived') return 'Archived';
    if (!s) return '—';
    return s.charAt(0).toUpperCase() + s.slice(1);
  }

  function catIcon(tag) {
    const m = CAT_META[tag];
    return m ? m.icon : '📄';
  }

  function catLabel(tag) {
    const m = CAT_META[tag];
    return m ? m.label : tag || 'Document';
  }

  function diClass(tag) {
    const t = (tag || 'other').toLowerCase();
    const map = ['onboarding', 'contracts', 'policies', 'manuals', 'reports'];
    if (map.includes(t)) return 'di-' + t;
    return 'di-internal';
  }

  function toast(msg, bad) {
    const el = document.getElementById('dhToast');
    if (!el) return;
    el.textContent = msg;
    el.classList.toggle('dh-toast--err', !!bad);
    el.classList.add('show');
    setTimeout(() => {
      el.classList.remove('show');
      el.classList.remove('dh-toast--err');
    }, 2800);
  }

  function slugifyHeading(s) {
    return String(s || '')
      .trim()
      .toLowerCase()
      .replace(/[^a-z0-9\s-]/g, '')
      .replace(/\s+/g, '-')
      .replace(/-+/g, '-')
      .replace(/^-|-$/g, '')
      .slice(0, 60) || 'section';
  }

  function ensureHeadingIds(root) {
    const used = {};
    root.querySelectorAll('h2, h3').forEach(el => {
      if (el.id) return;
      let base = slugifyHeading(el.textContent);
      let id = base;
      let n = 0;
      while (used[id]) {
        n++;
        id = base + '-' + n;
      }
      used[id] = true;
      el.id = id;
    });
  }

  function refreshTOC() {
    const contentEl = document.getElementById('dhEditorContent');
    const listEl = document.getElementById('dhTocListEdit');
    if (!contentEl || !listEl) return;
    ensureHeadingIds(contentEl);
    listEl.innerHTML = '';
    contentEl.querySelectorAll('h2, h3').forEach(h => {
      const a = document.createElement('a');
      a.href = '#' + h.id;
      a.textContent = (h.textContent || '').trim().slice(0, 100);
      a.className = 'toc-item';
      if (h.tagName === 'H3') a.style.paddingLeft = '20px';
      a.addEventListener('click', e => {
        e.preventDefault();
        h.scrollIntoView({ behavior: 'smooth', block: 'start' });
      });
      const li = document.createElement('li');
      li.style.listStyle = 'none';
      li.appendChild(a);
      listEl.appendChild(li);
    });
  }

  function canDeleteDoc(doc) {
    if (!doc) return false;
    return !!dhCanEdit;
  }

  async function getMe() {
    try {
      const r = await apiFetch('/api/auth/me', { headers: jsonHeaders() });
      if (!r.ok) return;
      const j = await r.json();
      me = j.user || j.data?.user || null;
      const av = document.getElementById('dhUserAv');
      const nm = document.getElementById('dhUserName');
      const rl = document.getElementById('dhUserRole');
      if (me) {
        const fn = (me.full_name || me.username || '').trim();
        const inits = fn
          .split(/\s+/)
          .map(p => p[0])
          .join('')
          .slice(0, 2)
          .toUpperCase() || '?';
        if (av) av.textContent = inits;
        if (nm) nm.textContent = fn || me.username || 'User';
        if (rl) rl.textContent = (me.role || 'user').charAt(0).toUpperCase() + (me.role || '').slice(1);
      }
    } catch (e) {}
  }

  function setSaveDots(mode) {
    const map = { clean: '', saved: 'saved', unsaved: 'unsaved' };
    const cls = map[mode] || '';
    const dot = document.getElementById('dhSaveDot');
    if (dot) dot.className = 'save-dot ' + cls;
    const label =
      mode === 'saved' ? 'Saved' : mode === 'unsaved' ? 'Unsaved changes' : 'No changes';
    const lbl = document.getElementById('dhSaveLabel');
    if (lbl) lbl.textContent = label;
  }

  function markDirty() {
    dirty = true;
    setSaveDots('unsaved');
    const ec = document.getElementById('dhEditorContent');
    if (ec) {
      const w = stripHtml(ec.innerHTML)
        .split(/\s+/)
        .filter(Boolean).length;
      const words = w.toLocaleString() + ' words';
      document.querySelectorAll('[data-dh-info="words"]').forEach(el => {
        el.textContent = words;
      });
    }
    clearTimeout(tocTimer);
    tocTimer = setTimeout(refreshTOC, 400);
  }

  function updateKpis() {}

  function visibleDocs() {
    const now = Math.floor(Date.now() / 1000);
    const recentCutoff = now - 30 * 24 * 60 * 60;
    const fb =
      filterBucket === 'analytics' ? 'all' : filterBucket;
    return docs.filter(d => {
      if (fb === 'published' && d.status !== 'published') return false;
      if (fb === 'draft' && d.status !== 'draft') return false;
      if (fb === 'review' && d.status !== 'review') return false;
      if (fb === 'archived' && d.status !== 'archived') return false;
      if (fb === 'uploads' && d.doc_type !== 'upload') return false;
      if (fb === 'internal' && (d.tag || '').toLowerCase() !== 'internal') {
        return false;
      }
      if (fb === 'starred' && !d.starred) return false;
      if (fb === 'recent' && (d.dateTs || 0) < recentCutoff) return false;
      if (
        ['onboarding', 'contracts', 'policies', 'manuals', 'reports'].includes(fb)
      ) {
        if ((d.tag || '').toLowerCase() !== fb) return false;
      }
      if (searchQ) {
        const q = searchQ.toLowerCase();
        const blob = (
          (d.name || '') +
          ' ' +
          (d.tag || '') +
          ' ' +
          (d.author || '')
        ).toLowerCase();
        if (!blob.includes(q)) return false;
      }
      return true;
    });
  }

  function panelTitle() {
    if (filterBucket === 'all') return LABELS.all;
    if (filterBucket === 'analytics') return LABELS.analytics;
    return LABELS[filterBucket] || filterBucket;
  }

  const SB_NAV_BUCKETS = [
    'all',
    'published',
    'draft',
    'review',
    'starred',
    'recent',
    'onboarding',
    'contracts',
    'policies',
    'manuals',
    'reports'
  ];

  function isOtherFilter() {
    return !SB_NAV_BUCKETS.includes(filterBucket);
  }

  function docsForNavBucket(bucket) {
    const now = Math.floor(Date.now() / 1000);
    const recentCutoff = now - 30 * 24 * 60 * 60;
    const catBuckets = ['onboarding', 'contracts', 'policies', 'manuals', 'reports'];
    return docs.filter(d => {
      if (bucket === 'published' && d.status !== 'published') return false;
      if (bucket === 'draft' && d.status !== 'draft') return false;
      if (bucket === 'review' && d.status !== 'review') return false;
      if (bucket === 'starred' && !d.starred) return false;
      if (bucket === 'recent' && (d.dateTs || 0) < recentCutoff) return false;
      if (catBuckets.includes(bucket) && (d.tag || '').toLowerCase() !== bucket) {
        return false;
      }
      if (searchQ) {
        const q = searchQ.toLowerCase();
        const blob = (
          (d.name || '') +
          ' ' +
          (d.tag || '') +
          ' ' +
          (d.author || '')
        ).toLowerCase();
        if (!blob.includes(q)) return false;
      }
      return true;
    });
  }

  function renderSbDocRowHtml(doc) {
    const sel = currentDocId === doc.id ? 'selected' : '';
    return `<div class="sb-doc-item ${sel}" data-doc-id="${doc.id}">
      <span class="sb-doc-title">${esc(doc.name)}</span>
    </div>`;
  }

  function bindSbDocList(el) {
    if (!el) return;
    el.querySelectorAll('.sb-doc-item').forEach(row => {
      row.onclick = () => selectDoc(Number(row.dataset.docId));
    });
  }

  function renderSbDocList(containerId, list) {
    const el = document.getElementById(containerId);
    if (!el) return;
    if (!list.length) {
      el.innerHTML =
        '<div class="sb-doc-empty">No documents</div>';
      return;
    }
    el.innerHTML = list.map(renderSbDocRowHtml).join('');
    bindSbDocList(el);
  }

  function syncSbBucketOpenState() {
    const other = isOtherFilter();
    document.querySelectorAll('.dh-sb-bucket[data-bucket]').forEach(wrap => {
      const b = wrap.dataset.bucket;
      const shouldOpen =
        !other && filterBucket === b && !sbCollapsedBuckets.has(b);
      wrap.classList.toggle('dh-sb-bucket--open', shouldOpen);
    });
    const sec = document.getElementById('dhSbOtherSection');
    if (sec) sec.hidden = !other;
  }

  function renderDocList() {
    renderSbDocList('dhSbDocsAll', docsForNavBucket('all'));
    renderSbDocList('dhSbDocsPublished', docsForNavBucket('published'));
    renderSbDocList('dhSbDocsDraft', docsForNavBucket('draft'));
    renderSbDocList('dhSbDocsReview', docsForNavBucket('review'));
    renderSbDocList('dhSbDocsStarred', docsForNavBucket('starred'));
    renderSbDocList('dhSbDocsRecent', docsForNavBucket('recent'));
    renderSbDocList('dhSbDocsOnboarding', docsForNavBucket('onboarding'));
    renderSbDocList('dhSbDocsContracts', docsForNavBucket('contracts'));
    renderSbDocList('dhSbDocsPolicies', docsForNavBucket('policies'));
    renderSbDocList('dhSbDocsManuals', docsForNavBucket('manuals'));
    renderSbDocList('dhSbDocsReports', docsForNavBucket('reports'));
    renderSbDocList('dhSbDocsOther', visibleDocs());

    const setCount = (id, n) => {
      const c = document.getElementById(id);
      if (c) c.textContent = n;
    };
    setCount('dhSbCountAll', docsForNavBucket('all').length);
    setCount('dhSbCountPublished', docsForNavBucket('published').length);
    setCount('dhSbCountDraft', docsForNavBucket('draft').length);
    setCount('dhSbCountReview', docsForNavBucket('review').length);
    setCount('dhSbCountStarred', docsForNavBucket('starred').length);
    setCount('dhSbCountRecent', docsForNavBucket('recent').length);
    setCount('dhSbCountOnboarding', docsForNavBucket('onboarding').length);
    setCount('dhSbCountContracts', docsForNavBucket('contracts').length);
    setCount('dhSbCountPolicies', docsForNavBucket('policies').length);
    setCount('dhSbCountManuals', docsForNavBucket('manuals').length);
    setCount('dhSbCountReports', docsForNavBucket('reports').length);
    setCount('dhSbOtherCount', visibleDocs().length);

    const osl = document.getElementById('dhSbOtherSectionLabel');
    if (osl) osl.textContent = panelTitle();

    syncSbBucketOpenState();
  }

  function syncTabStyles() {
    document.querySelectorAll('.dh-view-tab').forEach(t => {
      const k = t.getAttribute('data-tab');
      let on = false;
      if (k === 'library' && filterBucket === 'all') on = true;
      else if (k === 'published' && filterBucket === 'published') on = true;
      else if (k === 'starred' && filterBucket === 'starred') on = true;
      else if (k === 'recent' && filterBucket === 'recent') on = true;
      t.classList.toggle('active', on);
    });
    document.querySelectorAll('.dh-sb-bucket-head[data-filter]').forEach(h => {
      const f = h.getAttribute('data-filter');
      h.classList.toggle('active', filterBucket === f);
    });
    document.querySelectorAll('.sb-nav-item[data-filter]').forEach(n => {
      const f = n.getAttribute('data-filter');
      n.classList.toggle('active', filterBucket === f);
    });
  }

  window.dhSelectSbBucket = function (fb, headEl) {
    if (
      filterBucket === fb &&
      SB_NAV_BUCKETS.includes(fb) &&
      !isOtherFilter()
    ) {
      if (sbCollapsedBuckets.has(fb)) {
        sbCollapsedBuckets.delete(fb);
      } else {
        sbCollapsedBuckets.add(fb);
      }
      syncSbBucketOpenState();
      return;
    }
    filterDocs(fb, headEl);
  };

  function showEmpty() {
    revokeUploadPreviewUrl();
    currentDocId = null;
    viewMode = 'view';
    setDocInfoWrapsVisible(false);
    document.getElementById('dhEmptyState').style.display = 'flex';
    document.getElementById('dhViewerState').style.display = 'none';
    document.getElementById('dhEditorState').style.display = 'none';
    renderDocList();
  }

  function exportContentAsHtml(doc) {
    const html = `<!DOCTYPE html><html><head><meta charset="utf-8"><title>${esc(
      doc.name
    )}</title></head><body>${doc.content || ''}</body></html>`;
    const blob = new Blob([html], { type: 'text/html' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = (doc.name || 'document').replace(/[^a-z0-9.-]/gi, '_') + '.html';
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
    toast('Exported as HTML');
  }

  async function downloadFileDoc(id) {
    const r = await apiFetch('/api/docs/' + id + '/download', {});
    if (!r.ok) {
      toast('Download failed', true);
      return;
    }
    const blob = await r.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    const doc = docs.find(d => d.id === id);
    a.download = (doc && doc.filename) || 'document';
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  }

  function setDocInfoWrapsVisible(on) {
    ['dhViewerInfoWrap', 'dhEditorInfoWrap'].forEach(id => {
      const el = document.getElementById(id);
      if (el) el.hidden = !on;
    });
  }

  function setInfoField(key, val) {
    document.querySelectorAll('[data-dh-info="' + key + '"]').forEach(el => {
      el.textContent = val;
    });
  }

  function fillInfoPanel(doc) {
    setInfoField('cat', catLabel(doc.tag));
    setInfoField('status', statusLabel(doc.status));
    setInfoField('author', doc.author || '—');
    setInfoField('modified', doc.date || '—');
    if (doc.doc_type === 'content') {
      const w = stripHtml(doc.content || '')
        .split(/\s+/)
        .filter(Boolean).length;
      setInfoField('words', w.toLocaleString() + ' words');
    } else {
      setInfoField('words', doc.size || '—');
    }
  }

  async function renderUploadPreview(doc) {
    const vc = document.getElementById('dhViewerContent');
    if (!vc) return;
    const docId = doc.id;
    const kind = uploadPreviewKind(doc.type);
    if (kind === 'none') {
      vc.innerHTML = `
      <div class="dh-upload-card">
        <div class="dh-upload-icon">📎</div>
        <h2>${esc(doc.name)}</h2>
        <p style="color:var(--ink-3);margin-bottom:12px">${esc(doc.filename || '')} · ${esc(
        doc.type || ''
      )} · ${esc(doc.size || '')}</p>
        <p class="dh-preview-fallback-msg">In-browser preview isn’t available for this file type (e.g. Word, Excel, PowerPoint, or ZIP). Use <strong>Download</strong> to open it on your device.</p>
      </div>`;
      return;
    }

    vc.innerHTML =
      '<div class="dh-preview-loading"><span class="dh-preview-loading-inner">Loading preview…</span></div>';

    const r = await apiFetch('/api/docs/' + docId + '/download', {});
    if (currentDocId !== docId) return;
    if (!r.ok) {
      vc.innerHTML =
        '<p class="dh-preview-error">Could not load this file for preview. Try Download instead.</p>';
      toast('Preview failed', true);
      return;
    }

    if (kind === 'pdf') {
      const buf = await r.arrayBuffer();
      if (currentDocId !== docId) return;
      await renderPdfWithPdfJs(buf, docId, vc, doc.name);
      return;
    }

    if (kind === 'image') {
      const buf = await r.arrayBuffer();
      if (currentDocId !== docId) return;
      const ext = (doc.type || '').toLowerCase();
      const mimeMap = {
        png: 'image/png',
        jpg: 'image/jpeg',
        jpeg: 'image/jpeg',
        gif: 'image/gif',
        webp: 'image/webp'
      };
      const blob = new Blob([buf], { type: mimeMap[ext] || 'application/octet-stream' });
      revokeUploadPreviewUrl();
      dhUploadPreviewUrl = URL.createObjectURL(blob);
      vc.innerHTML = '';
      const wrap = document.createElement('div');
      wrap.className = 'dh-img-preview-wrap';
      const img = document.createElement('img');
      img.className = 'dh-preview-img';
      img.alt = doc.name || '';
      img.src = dhUploadPreviewUrl;
      img.loading = 'lazy';
      img.onerror = () => {
        wrap.innerHTML =
          '<p class="dh-preview-error">Could not display this image. Try Download instead.</p>';
      };
      wrap.appendChild(img);
      vc.appendChild(wrap);
      return;
    }

    if (kind === 'markdown') {
      const text = await r.text();
      if (currentDocId !== docId) return;
      vc.innerHTML = `<article class="dh-md-preview"><pre class="dh-md-pre">${esc(text)}</pre></article>`;
      return;
    }
  }

  function showUploadViewer(doc) {
    revokeUploadPreviewUrl();
    const fv = document.getElementById('dhRefDocsFooterViewer');
    const fe = document.getElementById('dhRefDocsFooterEditor');
    if (fv) fv.style.display = 'none';
    if (fe) fe.style.display = 'none';
    document.getElementById('dhEmptyState').style.display = 'none';
    document.getElementById('dhEditorState').style.display = 'none';
    document.getElementById('dhViewerState').style.display = 'flex';
    setDocInfoWrapsVisible(true);
    const tabs = document.getElementById('dhViewerModeTabs');
    if (tabs) tabs.style.display = 'none';

    document.getElementById('dhViewDocTitle').textContent = doc.name;
    void renderUploadPreview(doc);
    fillInfoPanel(doc);

    const star = document.getElementById('dhViewerStar');
    star.textContent = doc.starred ? '★ Starred' : '☆ Star';
    star.onclick = () => toggleStarById(doc.id);

    document.getElementById('dhViewerDownload').style.display = 'inline-flex';
    document.getElementById('dhViewerDownload').textContent = '⬇ Download';
    document.getElementById('dhViewerDownload').onclick = () => downloadFileDoc(doc.id);

    const pub = document.getElementById('dhViewerPublish');
    pub.style.display = dhCanEdit ? 'inline-flex' : 'none';
    pub.disabled = doc.status === 'published';
    pub.textContent = doc.status === 'published' ? 'Published' : '↑ Publish';
    pub.onclick = () => publishDocument(doc.id);

    document.getElementById('dhViewerDelete').style.display = canDeleteDoc(doc)
      ? 'inline-flex'
      : 'none';
    document.getElementById('dhViewerDelete').onclick = () => deleteDocument(doc.id);
  }

  function showContentViewer(doc) {
    revokeUploadPreviewUrl();
    document.getElementById('dhEmptyState').style.display = 'none';
    document.getElementById('dhEditorState').style.display = 'none';
    document.getElementById('dhViewerState').style.display = 'flex';
    setDocInfoWrapsVisible(true);
    const tabs = document.getElementById('dhViewerModeTabs');
    if (tabs) tabs.style.display = 'flex';

    document.getElementById('dhViewDocTitle').textContent = doc.name;
    document.getElementById('dhViewerContent').innerHTML =
      doc.content || '<p style="color:var(--ink-4)">No content yet.</p>';
    fillInfoPanel(doc);

    document.getElementById('dhViewerStar').textContent = doc.starred ? '★ Starred' : '☆ Star';
    document.getElementById('dhViewerStar').onclick = () => toggleStarById(doc.id);

    document.getElementById('dhViewerDownload').style.display = 'inline-flex';
    document.getElementById('dhViewerDownload').textContent = '⬇ Export';
    document.getElementById('dhViewerDownload').onclick = () => exportContentAsHtml(doc);

    const pub = document.getElementById('dhViewerPublish');
    pub.style.display = dhCanEdit ? 'inline-flex' : 'none';
    pub.disabled = doc.status === 'published';
    pub.textContent = doc.status === 'published' ? 'Published' : '↑ Publish';
    pub.onclick = () => publishDocument(doc.id);

    document.getElementById('dhViewerDelete').style.display = canDeleteDoc(doc)
      ? 'inline-flex'
      : 'none';
    document.getElementById('dhViewerDelete').onclick = () => deleteDocument(doc.id);

    syncViewerModeTabs('view');
    viewMode = 'view';
    renderRefDocsBar(doc);
  }

  function setStatusBadge(status) {
    currentEditorStatus = status || 'draft';
    const badge = document.getElementById('dhStatusBadge');
    const pip = document.getElementById('dhStatusPip');
    const txt = document.getElementById('dhStatusText');
    const map = {
      draft: ['sb-draft', 'sd-draft', 'Draft'],
      review: ['sb-review', 'sd-review', 'In Review'],
      published: ['sb-published', 'sd-published', 'Published'],
      archived: ['sb-archived', 'sd-draft', 'Archived']
    };
    const row = map[status] || map.draft;
    badge.className = 'status-badge ' + row[0];
    pip.className = 'status-dot ' + row[1];
    txt.textContent = row[2];
  }

  function showContentEditor(doc) {
    if (!dhCanEdit) {
      toast('Only administrators can edit documents', true);
      return;
    }
    revokeUploadPreviewUrl();
    document.getElementById('dhEmptyState').style.display = 'none';
    document.getElementById('dhViewerState').style.display = 'none';
    document.getElementById('dhEditorState').style.display = 'flex';
    setDocInfoWrapsVisible(true);
    document.getElementById('dhDocTitleInput').value = doc.name || '';
    const ec = document.getElementById('dhEditorContent');
    ec.innerHTML = doc.content || '<p></p>';
    ec.oninput = markDirty;
    setStatusBadge(doc.status);
    dirty = false;
    setSaveDots('clean');
    refreshTOC();
    syncEditorModeTabs('edit');
    fillInfoPanel(doc);
    viewMode = 'edit';
    renderRefDocsBar(doc);
  }

  function syncViewerModeTabs(mode) {
    document.querySelectorAll('#dhViewerModeTabs .mode-tab').forEach(b => {
      b.classList.toggle('active', b.getAttribute('data-mode') === mode);
    });
  }

  function syncEditorModeTabs(mode) {
    document.querySelectorAll('#dhEditorModeTabs .mode-tab').forEach(b => {
      b.classList.toggle('active', b.getAttribute('data-mode') === mode);
    });
  }

  function setMode(mode) {
    const doc = docs.find(d => d.id === currentDocId);
    if (!doc) return;
    if (doc.doc_type === 'upload') {
      if (mode === 'edit') toast('Uploaded files cannot be edited here', true);
      return;
    }
    if (mode === 'view') {
      if (dirty && !confirm('Discard unsaved changes?')) return;
      dirty = false;
      showContentViewer(doc);
      viewMode = 'view';
    } else if (mode === 'edit') {
      if (!dhCanEdit) {
        toast('Only administrators can edit documents', true);
        return;
      }
      showContentEditor(doc);
    }
  }

  function closeDocInfoDropdowns() {
    document.querySelectorAll('.dh-doc-info-dropdown').forEach(d => {
      d.hidden = true;
    });
    document.querySelectorAll('.dh-doc-info-btn').forEach(b => b.setAttribute('aria-expanded', 'false'));
  }

  function selectDoc(id) {
    if (dirty && !confirm('Discard unsaved changes?')) return;
    dirty = false;
    closeDocInfoDropdowns();
    currentDocId = id;
    const doc = docs.find(d => d.id === id);
    if (!doc) {
      showEmpty();
      return;
    }
    if (doc.doc_type === 'upload') {
      showUploadViewer(doc);
    } else {
      showContentViewer(doc);
    }
    viewMode = 'view';
    renderDocList();
  }

  async function patchDoc(id, data) {
    const r = await apiFetch('/api/docs/' + id, {
      method: 'PATCH',
      headers: jsonHeaders(),
      body: JSON.stringify(data)
    });
    const j = await r.json().catch(() => ({}));
    if (!r.ok || j.success === false) {
      toast(j.error || j.message || 'Update failed', true);
      return false;
    }
    const updated = j.document || j.data?.document;
    if (updated) {
      const idx = docs.findIndex(d => Number(d.id) === Number(id));
      if (idx >= 0) docs[idx] = { ...docs[idx], ...updated };
    }
    return true;
  }

  async function toggleStarById(id) {
    const doc = docs.find(d => d.id === id);
    if (!doc) return;
    const next = !doc.starred;
    const ok = await patchDoc(id, { starred: next });
    if (!ok) return;
    const d = docs.find(x => x.id === id);
    updateKpis();
    renderDocList();
    if (currentDocId === id && d) {
      const star = document.getElementById('dhViewerStar');
      if (star) star.textContent = d.starred ? '★ Starred' : '☆ Star';
    }
  }

  async function publishDocument(id) {
    if (!dhCanEdit) return;
    const ok = await patchDoc(id, { status: 'published' });
    if (!ok) return;
    toast('Document published');
    updateKpis();
    renderDocList();
    if (currentDocId === id) selectDoc(id);
  }

  async function deleteDocument(id) {
    const delId = id != null ? id : currentDocId;
    if (!delId) return;
    if (!confirm('Delete this document?')) return;
    const r = await apiFetch('/api/docs/' + delId, { method: 'DELETE' });
    const j = await r.json().catch(() => ({}));
    if (!r.ok) {
      toast(j.error || 'Delete failed', true);
      return;
    }
    toast('Document deleted');
    currentDocId = null;
    dirty = false;
    await loadDocs(false);
    showEmpty();
  }

  async function saveDoc() {
    if (!dhCanEdit || !currentDocId) return;
    const doc = docs.find(d => d.id === currentDocId);
    if (!doc || doc.doc_type !== 'content') return;

    const title =
      document.getElementById('dhDocTitleInput').value.trim() || doc.name;
    const content = document.getElementById('dhEditorContent').innerHTML;
    const ok = await patchDoc(currentDocId, {
      name: title,
      content,
      status: currentEditorStatus
    });
    if (ok) {
      dirty = false;
      setSaveDots('saved');
      toast('Document saved');
      updateKpis();
      renderDocList();
      const fresh = docs.find(x => x.id === currentDocId);
      if (fresh && viewMode === 'edit') {
        document.getElementById('dhDocTitleInput').value = fresh.name || '';
        fillInfoPanel(fresh);
        setStatusBadge(fresh.status);
        renderRefDocsBar(fresh);
      }
      setTimeout(() => setSaveDots('clean'), 2000);
    }
  }

  function cycleStatus() {
    if (!dhCanEdit || !currentDocId) return;
    const order = ['draft', 'review', 'published'];
    const i = order.indexOf(currentEditorStatus);
    currentEditorStatus = order[(i + 1) % order.length];
    setStatusBadge(currentEditorStatus);
    markDirty();
  }

  function applyWriteUI() {
    ['dhNewDocBtn', 'dhUploadBtn', 'dhEmptyNewBtn', 'dhEmptyUploadBtn'].forEach(id => {
      const el = document.getElementById(id);
      if (el) el.style.display = dhCanEdit ? '' : 'none';
    });
    const adm = document.getElementById('dhAdminAccessBtn');
    if (adm) adm.style.display = dhIsAdmin ? 'inline-flex' : 'none';
    const an = document.getElementById('dhAccessNavBtn');
    if (an) an.style.display = dhIsAdmin ? 'flex' : 'none';
  }

  /** Hide Edit tab and editor toolbar for non-admin users. */
  function applyEditChrome() {
    document.querySelectorAll('.mode-tab[data-mode="edit"]').forEach(b => {
      b.style.display = dhCanEdit ? '' : 'none';
    });
    const etb = document.querySelector('#dhEditorState .editor-toolbar');
    if (etb) etb.style.display = dhCanEdit ? '' : 'none';
  }

  async function loadDocs(selectAfter) {
    const a = await apiFetch('/api/docs/access-check', { headers: jsonHeaders() });
    if (a.status === 401) {
      window.location.href = '/login';
      return;
    }
    const aj = await a.json().catch(() => ({}));
    const allow = aj.allowed ?? aj.data?.allowed;
    const isAdmin = aj.is_admin ?? aj.data?.is_admin;
    if (!allow && !isAdmin) {
      dhCanWrite = false;
      dhCanEdit = false;
      dhIsAdmin = false;
      const denied =
        '<div class="sb-doc-empty" style="padding:12px">Access denied. Contact your admin.</div>';
      [
        'dhSbDocsAll',
        'dhSbDocsPublished',
        'dhSbDocsDraft',
        'dhSbDocsReview',
        'dhSbDocsStarred',
        'dhSbDocsRecent',
        'dhSbDocsOnboarding',
        'dhSbDocsContracts',
        'dhSbDocsPolicies',
        'dhSbDocsManuals',
        'dhSbDocsReports',
        'dhSbDocsOther'
      ].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.innerHTML = denied;
      });
      return;
    }
    dhIsAdmin = !!isAdmin;
    dhCanWrite = true;
    dhCanEdit = !!isAdmin;

    const r = await apiFetch('/api/docs', { headers: jsonHeaders() });
    const j = await r.json().catch(() => ({}));
    if (!r.ok || j.success === false) {
      toast(j.error || 'Failed to load documents', true);
      return;
    }
    docs = j.documents || j.data?.documents || [];
    updateKpis();
    renderDocList();
    applyWriteUI();
    applyEditChrome();

    if (currentDocId != null) {
      const d = docs.find(x => Number(x.id) === Number(currentDocId));
      if (d && d.doc_type === 'content') renderRefDocsBar(d);
    }

    if (selectAfter && currentDocId != null && docs.find(d => Number(d.id) === Number(currentDocId))) {
      selectDoc(currentDocId);
    } else if (!currentDocId) {
      setDocInfoWrapsVisible(false);
      document.getElementById('dhEmptyState').style.display = 'flex';
      document.getElementById('dhViewerState').style.display = 'none';
      document.getElementById('dhEditorState').style.display = 'none';
    }
    syncTabStyles();
  }

  function openNewModal() {
    document.getElementById('dhNewDocModal').classList.add('open');
    document.getElementById('dhNewTitle').value = '';
    document.getElementById('dhNewDesc').value = '';
    document.querySelectorAll('#dhTemplateGrid .template-item').forEach((x, i) => {
      x.classList.toggle('selected', i === 0);
    });
  }

  function closeNewModal() {
    document.getElementById('dhNewDocModal').classList.remove('open');
  }

  function openUploadModal() {
    document.getElementById('dhUploadModal').classList.add('open');
    const drop = document.getElementById('dhUploadDrop');
    if (drop) drop.classList.remove('dh-upload-drop--active');
    const fn = document.getElementById('dhUploadFileName');
    if (fn) fn.textContent = '';
  }

  function closeUploadModal() {
    document.getElementById('dhUploadModal').classList.remove('open');
    const drop = document.getElementById('dhUploadDrop');
    if (drop) drop.classList.remove('dh-upload-drop--active');
  }

  function initUploadDropZone() {
    const drop = document.getElementById('dhUploadDrop');
    const input = document.getElementById('dhUFile');
    const nameEl = document.getElementById('dhUploadFileName');
    if (!drop || !input) return;

    const setFileLabel = () => {
      const f = input.files && input.files[0];
      if (nameEl) nameEl.textContent = f ? f.name : '';
    };

    input.addEventListener('change', setFileLabel);

    drop.addEventListener('dragover', e => {
      e.preventDefault();
      e.stopPropagation();
      drop.classList.add('dh-upload-drop--active');
    });
    drop.addEventListener('dragleave', e => {
      if (!drop.contains(e.relatedTarget)) drop.classList.remove('dh-upload-drop--active');
    });
    drop.addEventListener('drop', e => {
      e.preventDefault();
      e.stopPropagation();
      drop.classList.remove('dh-upload-drop--active');
      const f = e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files[0];
      if (!f) return;
      try {
        const dt = new DataTransfer();
        dt.items.add(f);
        input.files = dt.files;
        setFileLabel();
      } catch (err) {
        toast('Could not use that file', true);
      }
    });

    drop.addEventListener('click', e => {
      if (e.target.closest('.dh-upload-browse')) return;
      input.click();
    });

    drop.addEventListener('keydown', e => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        input.click();
      }
    });

    const browse = drop.querySelector('.dh-upload-browse');
    if (browse) {
      browse.addEventListener('click', e => {
        e.preventDefault();
        e.stopPropagation();
        input.click();
      });
    }
  }

  async function createDoc() {
    if (!dhCanEdit) {
      toast('Only administrators can create documents', true);
      return;
    }
    const title = document.getElementById('dhNewTitle').value.trim();
    if (!title) {
      toast('Please enter a document title', true);
      return;
    }
    const sel = document.querySelector('#dhTemplateGrid .template-item.selected');
    const cat = sel ? sel.getAttribute('data-cat') || 'other' : 'other';
    const apiCat = cat === 'other' ? 'Internal' : cat;
    const content = TEMPLATES[cat] || TEMPLATES.other;
    const r = await apiFetch('/api/docs', {
      method: 'POST',
      headers: jsonHeaders(),
      body: JSON.stringify({
        title,
        category: apiCat,
        content,
        status: 'draft'
      })
    });
    const j = await r.json().catch(() => ({}));
    if (!r.ok || j.success === false) {
      toast(j.error || 'Create failed', true);
      return;
    }
    const newDoc = j.document || j.data?.document;
    closeNewModal();
    toast('Document created');
    await loadDocs(false);
    const nid = newDoc && newDoc.id;
    if (nid != null) {
      selectDoc(nid);
      const fresh = docs.find(d => d.id === nid);
      if (dhCanEdit && fresh && fresh.doc_type === 'content') showContentEditor(fresh);
    }
  }

  async function submitUpload() {
    if (!dhCanEdit) {
      toast('Only administrators can upload documents', true);
      return;
    }
    const file = document.getElementById('dhUFile').files[0];
    if (!file) {
      toast('Select a file first', true);
      return;
    }
    const fd = new FormData();
    fd.append('file', file);
    fd.append('name', document.getElementById('dhUName').value.trim());
    fd.append('category', document.getElementById('dhUCategory').value || 'Internal');
    fd.append('status', document.getElementById('dhUStatus').value || 'draft');
    const r = await apiFetch('/api/docs/upload', {
      method: 'POST',
      body: fd
    });
    const j = await r.json().catch(() => ({}));
    if (!r.ok || j.success === false) {
      toast(j.error || 'Upload failed', true);
      return;
    }
    closeUploadModal();
    document.getElementById('dhUName').value = '';
    document.getElementById('dhUFile').value = '';
    const ufn = document.getElementById('dhUploadFileName');
    if (ufn) ufn.textContent = '';
    toast('Document uploaded');
    await loadDocs(false);
    const created = j.documents || j.data?.documents;
    if (created && created[0] && created[0].id) selectDoc(created[0].id);
  }

  function switchShell() {
    syncTabStyles();
  }

  window.switchView = function (view, el) {
    if (view !== 'library') return;
    document.querySelectorAll('.sb-nav-item').forEach(e => e.classList.remove('active'));
    document.querySelectorAll('.dh-sb-bucket-head').forEach(e => e.classList.remove('active'));
    sbCollapsedBuckets.clear();
    filterBucket = 'all';
    const head = document.getElementById('dhSbHeadAll');
    if (head) head.classList.add('active');
    switchShell();
    renderDocList();
    syncTabStyles();
  };

  window.switchTab = function (tab, el) {
    if (tab === 'library') {
      sbCollapsedBuckets.clear();
      filterBucket = 'all';
      switchShell();
      renderDocList();
      syncTabStyles();
      if (el && el.classList) {
        document.querySelectorAll('.dh-view-tab').forEach(t => t.classList.remove('active'));
        el.classList.add('active');
      }
      return;
    }

    sbCollapsedBuckets.clear();
    if (tab === 'published') filterBucket = 'published';
    else if (tab === 'starred') filterBucket = 'starred';
    else if (tab === 'recent') filterBucket = 'recent';

    switchShell();
    renderDocList();
    syncTabStyles();
    if (el && el.classList) {
      document.querySelectorAll('.dh-view-tab').forEach(t => t.classList.remove('active'));
      el.classList.add('active');
    }
  };

  function ensureCategoriesGroupOpen() {
    const grp = document.getElementById('group-categories');
    const btn = document.getElementById('dhCategoriesToggle');
    if (!grp || grp.style.display !== 'none') return;
    grp.style.display = '';
    const ch = btn && btn.querySelector('.sb-chevron');
    if (ch) ch.classList.add('open');
  }

  window.filterDocs = function (f, el) {
    if (filterBucket !== f) {
      sbCollapsedBuckets.clear();
    }
    filterBucket = f;
    switchShell();
    document.querySelectorAll('.sb-nav-item').forEach(e => e.classList.remove('active'));
    document.querySelectorAll('.dh-sb-bucket-head').forEach(e => e.classList.remove('active'));
    if (el) el.classList.add('active');
    if (['onboarding', 'contracts', 'policies', 'manuals', 'reports'].includes(f)) {
      ensureCategoriesGroupOpen();
    }
    renderDocList();
    syncTabStyles();
  };

  window.toggleGroup = function (id, btn) {
    const el = document.getElementById('group-' + id);
    const ch = btn.querySelector('.sb-chevron');
    if (!el) return;
    if (el.style.display === 'none') {
      el.style.display = '';
      if (ch) ch.classList.add('open');
    } else {
      el.style.display = 'none';
      if (ch) ch.classList.remove('open');
    }
  };

  window.dhOpenAccessModal = async function () {
    const r = await apiFetch('/api/admin/dochub/access-users', { headers: jsonHeaders() });
    const j = await r.json().catch(() => ({}));
    if (!r.ok) {
      toast(j.error || 'Failed to load', true);
      return;
    }
    const users = j.users || j.data?.users || [];
    const body = document.getElementById('dhAccessBody');
    body.innerHTML = users
      .map(
        u => `<tr style="border-bottom:1px solid var(--border)">
      <td style="padding:10px 12px">${esc(u.full_name || u.username)}</td>
      <td style="padding:10px 12px">${esc(u.email)}</td>
      <td style="padding:10px 12px">${esc(u.role)}</td>
      <td style="padding:10px 12px">${
        u.role === 'admin'
          ? '<span style="background:var(--accent-light);color:var(--accent);padding:3px 8px;border-radius:999px;font-size:11px;font-weight:600">Always allowed</span>'
          : `<label style="display:flex;align-items:center;gap:8px"><input type="checkbox" ${u.can_access_dochub ? 'checked' : ''} onchange="dhSetUserAccess(${u.id},this.checked)"> <span>${u.can_access_dochub ? 'Allowed' : 'Blocked'}</span></label>`
      }</td>
    </tr>`
      )
      .join('');
    document.getElementById('dhAccessModal').classList.add('open');
  };

  window.dhCloseAccessModal = function () {
    document.getElementById('dhAccessModal').classList.remove('open');
  };

  window.dhSetUserAccess = async function (userId, canAccess) {
    const r = await apiFetch('/api/admin/dochub/access-users/' + userId, {
      method: 'POST',
      headers: jsonHeaders(),
      body: JSON.stringify({ can_access: !!canAccess })
    });
    const j = await r.json().catch(() => ({}));
    if (!r.ok) toast(j.error || 'Failed', true);
    else toast('Access updated');
  };

  window.dhToggleSidebar = function () {
    const sb = document.getElementById('dhSidebar');
    const ov = document.getElementById('dhOverlay');
    if (sb && ov) {
      sb.classList.toggle('open');
      ov.classList.toggle('active', sb.classList.contains('open'));
      ov.setAttribute('aria-hidden', !sb.classList.contains('open'));
    }
  };

  window.dhCloseSidebar = function () {
    const sb = document.getElementById('dhSidebar');
    const ov = document.getElementById('dhOverlay');
    if (sb && ov) {
      sb.classList.remove('open');
      ov.classList.remove('active');
      ov.setAttribute('aria-hidden', 'true');
    }
  };

  function execCmd(cmd, val) {
    if (!dhCanEdit) return;
    const ec = document.getElementById('dhEditorContent');
    if (ec) ec.focus();
    document.execCommand(cmd, false, val || null);
    markDirty();
  }

  function insertHtml(html) {
    const ec = document.getElementById('dhEditorContent');
    if (!ec) return;
    ec.focus();
    try {
      document.execCommand('insertHTML', false, html);
    } catch (e) {
      toast('Could not insert content', true);
      return;
    }
    markDirty();
    refreshTOC();
  }

  function dhInsertReferenceDoc() {
    if (!dhCanEdit) {
      toast('Only administrators can attach additional documents', true);
      return;
    }
    const inp = document.getElementById('dhEditorRefInput');
    if (inp) inp.click();
  }

  async function uploadEditorImage(file) {
    if (!file || !dhCanEdit) return;
    const fd = new FormData();
    fd.append('file', file);
    const r = await apiFetch('/api/docs/inline-image', {
      method: 'POST',
      body: fd
    });
    const j = await r.json().catch(() => ({}));
    if (!r.ok || j.success === false) {
      toast(j.error || 'Image upload failed', true);
      return;
    }
    const url = j.url || (j.data && j.data.url);
    if (!url) {
      toast('Image upload failed', true);
      return;
    }
    const doc = docs.find(d => d.id === currentDocId);
    const alt = escAttr((doc && doc.name) || 'Image');
    insertHtml(
      '<p><img class="dh-inline-img" src="' + escAttr(url) + '" alt="' + alt + '" loading="lazy"/></p>'
    );
    toast('Image inserted');
  }

  function dhInsertImage() {
    if (!dhCanEdit) {
      toast('Only administrators can edit documents', true);
      return;
    }
    const inp = document.getElementById('dhEditorImageInput');
    if (inp) inp.click();
  }

  function dhOpenTableModal() {
    if (!dhCanEdit) {
      toast('Only administrators can edit documents', true);
      return;
    }
    const m = document.getElementById('dhTableModal');
    if (m) m.classList.add('open');
  }

  function dhCloseTableModal() {
    const m = document.getElementById('dhTableModal');
    if (m) m.classList.remove('open');
  }

  function dhInsertTableConfirm() {
    const r = parseInt(document.getElementById('dhTableRows').value, 10) || 3;
    const c = parseInt(document.getElementById('dhTableCols').value, 10) || 3;
    const header = document.getElementById('dhTableHeader').checked;
    const refEl = document.getElementById('dhTableRefCol');
    const refCol = refEl ? refEl.checked : false;
    const rows = Math.min(30, Math.max(1, r));
    const cols = Math.min(20, Math.max(1, c));
    dhCloseTableModal();
    let html = '<table class="dh-editor-table">';
    if (header) {
      html += '<thead><tr>';
      for (let i = 0; i < cols; i++) html += '<th>&nbsp;</th>';
      if (refCol) html += '<th>Additional document</th>';
      html += '</tr></thead>';
    } else if (refCol) {
      html += '<thead><tr>';
      for (let i = 0; i < cols; i++) html += '<th>&nbsp;</th>';
      html += '<th>Additional document</th></tr></thead>';
    }
    const dataRows = header ? rows - 1 : rows;
    if (dataRows > 0) {
      html += '<tbody>';
      for (let rr = 0; rr < dataRows; rr++) {
        html += '<tr>';
        for (let cc = 0; cc < cols; cc++) html += '<td>&nbsp;</td>';
        if (refCol) {
          html +=
            '<td class="dh-ref-cell"><span class="dh-ref-hint">Additional documents at the bottom of the page</span></td>';
        }
        html += '</tr>';
      }
      html += '</tbody>';
    }
    html += '</table><p><br></p>';
    insertHtml(html);
  }

  function dhInsertLink() {
    if (!dhCanEdit) {
      toast('Only administrators can edit documents', true);
      return;
    }
    const url = window.prompt('Paste link URL (https://…):');
    if (!url || !String(url).trim()) return;
    const ec = document.getElementById('dhEditorContent');
    if (ec) ec.focus();
    document.execCommand('createLink', false, url.trim());
    markDirty();
  }

  window.closeNewModal = closeNewModal;
  window.closeUploadModal = closeUploadModal;
  window.openNewModal = openNewModal;
  window.openUploadModal = openUploadModal;
  window.createDoc = createDoc;
  window.submitUpload = submitUpload;
  window.setMode = setMode;
  window.saveDoc = saveDoc;
  window.cycleStatus = cycleStatus;
  window.execCmd = execCmd;
  window.markUnsaved = markDirty;
  window.dhInsertImage = dhInsertImage;
  window.dhOpenTableModal = dhOpenTableModal;
  window.dhCloseTableModal = dhCloseTableModal;
  window.dhInsertTableConfirm = dhInsertTableConfirm;
  window.dhInsertLink = dhInsertLink;
  window.dhInsertReferenceDoc = dhInsertReferenceDoc;
  window.searchDocs = function (q) {
    searchQ = String(q || '').trim();
    renderDocList();
  };
  window.toggleStar = function () {
    if (currentDocId != null) toggleStarById(currentDocId);
  };
  window.publishDoc = function () {
    if (currentDocId != null) publishDocument(currentDocId);
  };
  window.deleteDoc = function () {
    deleteDocument(currentDocId);
  };

  window.dhToggleDocInfo = function (ev, panelId) {
    ev.stopPropagation();
    const p = document.getElementById(panelId);
    const btn = ev.currentTarget;
    if (!p || !btn) return;
    const willOpen = p.hidden;
    document.querySelectorAll('.dh-doc-info-dropdown').forEach(d => {
      d.hidden = true;
    });
    document.querySelectorAll('.dh-doc-info-btn').forEach(b => b.setAttribute('aria-expanded', 'false'));
    if (willOpen) {
      p.hidden = false;
      btn.setAttribute('aria-expanded', 'true');
    }
  };

  document.addEventListener('click', e => {
    if (e.target.closest('.dh-doc-info-wrap')) return;
    closeDocInfoDropdowns();
  });

  document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('#dhTemplateGrid .template-item').forEach(el => {
      el.addEventListener('click', () => {
        document
          .querySelectorAll('#dhTemplateGrid .template-item')
          .forEach(x => x.classList.remove('selected'));
        el.classList.add('selected');
      });
    });

    const bind = (id, fn) => {
      const n = document.getElementById(id);
      if (n) n.onclick = fn;
    };
    bind('dhNewDocBtn', openNewModal);
    bind('dhUploadBtn', openUploadModal);
    bind('dhEmptyNewBtn', openNewModal);
    bind('dhEmptyUploadBtn', openUploadModal);
    bind('dhEditorSaveBtn', saveDoc);

    const stBadge = document.getElementById('dhStatusBadge');
    if (stBadge) stBadge.onclick = cycleStatus;

    const fmt = document.getElementById('dhFormatSelect');
    if (fmt) {
      fmt.onchange = function () {
        const v = this.value;
        if (v === 'p' || v === 'h1' || v === 'h2' || v === 'h3') {
          execCmd('formatBlock', v);
        }
        this.value = 'p';
      };
    }

    const imgIn = document.getElementById('dhEditorImageInput');
    if (imgIn) {
      imgIn.addEventListener('change', async () => {
        const f = imgIn.files && imgIn.files[0];
        imgIn.value = '';
        if (f) await uploadEditorImage(f);
      });
    }

    function wireAdditionalDocInput(el) {
      if (!el || el._dhAdditionalDocBound) return;
      el._dhAdditionalDocBound = true;
      el.addEventListener('change', async () => {
        // Snapshot File objects before clearing the input — clearing value empties the live FileList in most browsers.
        const files = Array.from(el.files || []);
        el.value = '';
        if (files.length) await addDocumentReferenceFiles(files);
      });
    }
    wireAdditionalDocInput(document.getElementById('dhEditorRefInput'));
    bindRefChipContainers();

    const edPaste = document.getElementById('dhEditorContent');
    if (edPaste) {
      edPaste.addEventListener('paste', async e => {
        if (!dhCanEdit || viewMode !== 'edit') return;
        const items = e.clipboardData && e.clipboardData.items;
        if (!items) return;
        for (let i = 0; i < items.length; i++) {
          if (items[i].type.indexOf('image') !== -1) {
            e.preventDefault();
            const file = items[i].getAsFile();
            if (file) await uploadEditorImage(file);
            return;
          }
        }
      });
    }

    document.addEventListener('keydown', e => {
      if ((e.ctrlKey || e.metaKey) && e.key === 's') {
        e.preventDefault();
        const doc = docs.find(d => d.id === currentDocId);
        if (doc && doc.doc_type === 'content' && viewMode === 'edit') saveDoc();
      }
      if (e.key === 'Escape') dhCloseSidebar();
    });

    initUploadDropZone();

    getMe().finally(() => {
      loadDocs(false);
    });
  });
})();
