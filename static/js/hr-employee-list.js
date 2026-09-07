/**
 * Employee List — filter staff cards by Emp ID or name (same roster as Leave Tracker).
 */
(function () {
  'use strict';

  var employees = [];
  var filtered = [];
  var selectedId = null;
  var currentEmp = null;
  var modalPane = 'view';
  var modalBusy = false;

  function $(id) {
    return document.getElementById(id);
  }

  function esc(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function authHeaders() {
    var h = { Accept: 'application/json' };
    var token = localStorage.getItem('access_token') || localStorage.getItem('token');
    if (token) h.Authorization = 'Bearer ' + token;
    return h;
  }

  function unwrap(body) {
    if (!body) return {};
    if (body.data != null && typeof body.data === 'object' && !Array.isArray(body.data)) {
      return Object.assign({}, body, body.data);
    }
    return body;
  }

  var TOAST_MS = 10000;

  function hideToast(force) {
    var el = $('elToast');
    if (!el) return;
    if (!force && toast._hovering) return;
    toast._hovering = false;
    clearTimeout(toast._t);
    el.classList.remove('is-show');
    clearTimeout(toast._hide);
    toast._hide = setTimeout(function () {
      if (!force && toast._hovering) return;
      el.hidden = true;
      el.classList.remove('is-error');
    }, 220);
  }

  function scheduleToastHide() {
    clearTimeout(toast._t);
    toast._t = setTimeout(hideToast, TOAST_MS);
  }

  function toast(msg, isError) {
    var el = $('elToast');
    var text = $('elToastMsg');
    if (!el) return;
    if (text) text.textContent = msg;
    else el.textContent = msg;
    el.hidden = false;
    el.classList.toggle('is-error', !!isError);
    el.classList.remove('is-show');
    el.setAttribute('role', isError ? 'alert' : 'status');
    toast._hovering = false;
    requestAnimationFrame(function () {
      el.classList.add('is-show');
    });
    scheduleToastHide();
  }

  function initials(name) {
    var parts = String(name || '').trim().split(/\s+/).filter(Boolean);
    if (!parts.length) return '?';
    var a = parts[0].charAt(0);
    var b = parts.length > 1 ? parts[parts.length - 1].charAt(0) : '';
    return (a + b).toUpperCase();
  }

  function queryNorm() {
    return (($('elSearch') && $('elSearch').value) || '').trim().toLowerCase();
  }

  function companyFilter() {
    return (($('elCompany') && $('elCompany').value) || 'all').trim();
  }

  function matchesQuery(emp, q) {
    if (!q) return true;
    var id = String(emp.emp_id || '').toLowerCase();
    var name = String(emp.full_name || '').toLowerCase();
    var desig = String(emp.designation || '').toLowerCase();
    var label = id + ' — ' + name;
    return id.indexOf(q) !== -1 || name.indexOf(q) !== -1 || desig.indexOf(q) !== -1 || label.indexOf(q) !== -1;
  }

  function currentRows() {
    var q = queryNorm();
    var company = companyFilter();
    return employees.filter(function (emp) {
      if (company && company !== 'all' && String(emp.company || '') !== company) return false;
      return matchesQuery(emp, q);
    });
  }

  function uniqueCompanies(list) {
    var seen = {};
    (list || []).forEach(function (e) {
      var c = (e.company || '').trim();
      if (c) seen[c] = true;
    });
    return Object.keys(seen).length;
  }

  function uniqueCompanyNames(list) {
    var seen = { Kynvera: true, Tourism: true, 'L&P': true };
    var names = ['Kynvera', 'Tourism', 'L&P'];
    (list || []).forEach(function (e) {
      var c = (e.company || '').trim();
      if (c && !seen[c]) {
        seen[c] = true;
        names.push(c);
      }
    });
    return names;
  }

  function refreshCompanyChoices() {
    var names = uniqueCompanyNames(employees);
    var filter = $('elCompany');
    if (filter) {
      var current = filter.value || 'all';
      filter.innerHTML =
        '<option value="all">All companies</option>' +
        names.map(function (n) {
          return '<option value="' + esc(n) + '">' + esc(n) + '</option>';
        }).join('');
      filter.value = current;
      if (filter.value !== current) filter.value = 'all';
    }
  }

  function renderGrid() {
    var grid = $('elGrid');
    var status = $('elStatus');
    var clearBtn = $('elSearchClear');
    filtered = currentRows();
    if (clearBtn) clearBtn.hidden = !queryNorm();
    if ($('elStatTotal')) $('elStatTotal').textContent = String(employees.length);
    if ($('elStatShown')) $('elStatShown').textContent = String(filtered.length);
    if ($('elStatCompanies')) $('elStatCompanies').textContent = String(uniqueCompanies(employees));

    if (!employees.length) {
      if (status) {
        status.hidden = false;
        status.textContent = 'No staff yet. Add employees from Leave Tracker.';
      }
      if (grid) {
        grid.hidden = true;
        grid.innerHTML = '';
      }
      return;
    }
    if (!filtered.length) {
      if (status) {
        status.hidden = false;
        status.textContent = 'No staff match that Emp ID or name.';
      }
      if (grid) {
        grid.hidden = true;
        grid.innerHTML = '';
      }
      return;
    }
    if (status) {
      status.hidden = true;
      status.textContent = '';
    }
    if (!grid) return;
    grid.hidden = false;
    grid.innerHTML = filtered.map(function (e) {
      var active = selectedId != null && String(e.id) === String(selectedId) ? ' is-active' : '';
      return (
        '<button type="button" class="el-card' + active + '" data-emp-open="' + e.id + '">' +
        '<span class="el-avatar">' + esc(initials(e.full_name)) + '</span>' +
        '<span class="el-card-body">' +
        '<span class="el-card-name">' + esc(e.full_name) + '</span>' +
        '<span class="el-card-role">' + esc(e.designation || '—') + '</span>' +
        '<span class="el-card-foot">' +
        '<span class="el-card-id">' + esc(e.emp_id || '—') + '</span>' +
        '<span class="el-company">' + esc(e.company || '—') + '</span>' +
        '</span></span></button>'
      );
    }).join('');
  }

  function findEmp(id) {
    var key = String(id);
    for (var i = 0; i < employees.length; i++) {
      if (String(employees[i].id) === key) return employees[i];
    }
    return null;
  }

  function showModalPane(pane) {
    modalPane = pane || 'view';
    var view = $('elViewPane');
    var form = $('elEditForm');
    var del = $('elDeletePane');
    if (view) view.hidden = modalPane !== 'view';
    if (form) form.hidden = modalPane !== 'edit';
    if (del) del.hidden = modalPane !== 'delete';
  }

  function fillEditForm(emp) {
    if (!emp) return;
    if ($('elEditEmpId')) $('elEditEmpId').value = emp.emp_id || '';
    if ($('elEditName')) $('elEditName').value = emp.full_name || '';
    if ($('elEditDesig')) $('elEditDesig').value = emp.designation || '';
    if ($('elEditCompany')) $('elEditCompany').value = emp.company || '';
    if ($('elEditEntitlement')) {
      $('elEditEntitlement').value = emp.annual_entitlement != null ? emp.annual_entitlement : '';
    }
  }

  function openModal(emp) {
    var modal = $('elModal');
    if (!modal || !emp) return;
    currentEmp = emp;
    selectedId = emp.id;
    $('elModalAvatar').textContent = initials(emp.full_name);
    $('elModalName').textContent = emp.full_name || '—';
    $('elModalEmpId').textContent = emp.emp_id || '—';
    $('elModalDesig').textContent = emp.designation || '—';
    $('elModalCompany').textContent = emp.company || '—';
    if ($('elDeleteAvatar')) $('elDeleteAvatar').textContent = initials(emp.full_name);
    if ($('elDeleteCopy')) {
      $('elDeleteCopy').textContent =
        (emp.full_name || 'This person') +
        (emp.emp_id ? ' (' + emp.emp_id + ')' : '') +
        ' will leave Employee List. Leave records stay in Leave Tracker.';
    }
    var leave = $('elModalLeaveLink');
    if (leave) leave.href = '/hr/leave-tracker';
    fillEditForm(emp);
    showModalPane('view');
    modal.hidden = false;
    document.body.style.overflow = 'hidden';
    renderGrid();
  }

  function closeModal() {
    var modal = $('elModal');
    if (modal) modal.hidden = true;
    showModalPane('view');
    if (!$('elAddModal') || $('elAddModal').hidden) {
      document.body.style.overflow = '';
    }
  }

  function apiJson(url, method, payload) {
    var headers = authHeaders();
    headers['Content-Type'] = 'application/json';
    var opts = {
      method: method,
      credentials: 'same-origin',
      headers: headers,
    };
    if (payload !== undefined) opts.body = JSON.stringify(payload);
    return fetch(url, opts).then(function (r) {
      return r.json().then(function (body) {
        if (!r.ok || body.success === false) {
          throw new Error((body && (body.error || body.message)) || 'Request failed');
        }
        return unwrap(body);
      });
    });
  }

  function submitEditEmployee() {
    if (!currentEmp || modalBusy) return Promise.resolve();
    var payload = {
      emp_id: ($('elEditEmpId') && $('elEditEmpId').value) || '',
      full_name: ($('elEditName') && $('elEditName').value) || '',
      designation: ($('elEditDesig') && $('elEditDesig').value) || '',
      company: ($('elEditCompany') && $('elEditCompany').value.trim()) || '',
    };
    var ent = $('elEditEntitlement') && $('elEditEntitlement').value;
    payload.annual_entitlement = ent ? Number(ent) : null;
    modalBusy = true;
    return apiJson('/hr/api/leave-tracker/employees/' + currentEmp.id, 'PATCH', payload).then(function () {
      showImportResult('Employee updated');
      closeModal();
      selectedId = null;
      currentEmp = null;
      return loadEmployees();
    }).finally(function () {
      modalBusy = false;
    });
  }

  function confirmDeleteEmployee() {
    if (!currentEmp || modalBusy) return Promise.resolve();
    var name = currentEmp.full_name || 'Employee';
    modalBusy = true;
    return apiJson('/hr/api/leave-tracker/employees/' + currentEmp.id, 'DELETE').then(function () {
      showImportResult(name + ' removed from the list');
      closeModal();
      selectedId = null;
      currentEmp = null;
      return loadEmployees();
    }).finally(function () {
      modalBusy = false;
    });
  }

  function loadEmployees() {
    var status = $('elStatus');
    if (status) {
      status.hidden = false;
      status.textContent = 'Loading staff…';
    }
    return fetch('/hr/api/leave-tracker/employees', {
      credentials: 'same-origin',
      headers: authHeaders(),
    }).then(function (r) {
      return r.json().then(function (body) {
        if (!r.ok || body.success === false) {
          throw new Error((body && (body.error || body.message)) || 'Request failed');
        }
        return unwrap(body);
      });
    }).then(function (data) {
      employees = data.employees || [];
      refreshCompanyChoices();
      renderGrid();
    }).catch(function (err) {
      if (status) {
        status.hidden = false;
        status.textContent = 'Could not load employees.';
      }
      toast(err.message || 'Could not load employees', true);
    });
  }

  function showImportResult(msg, isError) {
    toast(msg, isError);
  }

  function downloadBlob(url, filename) {
    return fetch(url, {
      credentials: 'same-origin',
      headers: authHeaders(),
    }).then(function (r) {
      if (!r.ok) throw new Error('Download failed');
      return r.blob();
    }).then(function (blob) {
      var a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
    });
  }

  function uploadImport(file) {
    var fd = new FormData();
    fd.append('file', file);
    return fetch('/hr/api/employee-list/import', {
      method: 'POST',
      credentials: 'same-origin',
      headers: authHeaders(),
      body: fd,
    }).then(function (r) {
      return r.json().then(function (body) {
        if (!r.ok || body.success === false) {
          throw new Error((body && (body.error || body.message)) || 'Import failed');
        }
        return unwrap(body);
      });
    }).then(function (data) {
      var extra = data.errors && data.errors.length ? '; issues: ' + data.errors.slice(0, 3).join('; ') : '';
      showImportResult(
        'Imported — added ' + (data.created || 0) +
          ', updated ' + (data.updated || 0) + extra
      );
      return loadEmployees();
    }).catch(function (err) {
      showImportResult(err.message, true);
    });
  }

  function openAddModal() {
    if ($('elAddForm')) $('elAddForm').reset();
    var modal = $('elAddModal');
    if (modal) modal.hidden = false;
    document.body.style.overflow = 'hidden';
    setTimeout(function () {
      $('elAddEmpId') && $('elAddEmpId').focus();
    }, 50);
  }

  function closeAddModal() {
    var modal = $('elAddModal');
    if (modal) modal.hidden = true;
    if (!$('elModal') || $('elModal').hidden) {
      document.body.style.overflow = '';
    }
  }

  function submitNewEmployee() {
    var payload = {
      emp_id: (($('elAddEmpId') && $('elAddEmpId').value) || '').trim(),
      full_name: (($('elAddName') && $('elAddName').value) || '').trim(),
      designation: (($('elAddDesig') && $('elAddDesig').value) || '').trim(),
      company: (($('elAddCompany') && $('elAddCompany').value) || '').trim(),
    };
    var ent = $('elAddEntitlement') && $('elAddEntitlement').value;
    if (ent) payload.annual_entitlement = Number(ent);
    var headers = authHeaders();
    headers['Content-Type'] = 'application/json';
    return fetch('/hr/api/leave-tracker/employees', {
      method: 'POST',
      credentials: 'same-origin',
      headers: headers,
      body: JSON.stringify(payload),
    }).then(function (r) {
      return r.json().then(function (body) {
        if (!r.ok || body.success === false) {
          throw new Error((body && (body.error || body.message)) || 'Could not add employee');
        }
        return unwrap(body);
      });
    }).then(function (data) {
      var emp = data.employee;
      closeAddModal();
      if ($('elSearch')) $('elSearch').value = '';
      if ($('elCompany')) $('elCompany').value = 'all';
      selectedId = emp && emp.id;
      if (emp && emp.id) {
        var found = false;
        for (var i = 0; i < employees.length; i++) {
          if (String(employees[i].id) === String(emp.id)) {
            employees[i] = emp;
            found = true;
            break;
          }
        }
        if (!found) employees.unshift(emp);
        refreshCompanyChoices();
        renderGrid();
      }
      showImportResult((emp && emp.full_name ? emp.full_name + ' added to the staff list' : 'Employee added to the staff list'));
      return loadEmployees();
    });
  }

  function bind() {
    var search = $('elSearch');
    var company = $('elCompany');
    var clearBtn = $('elSearchClear');
    var grid = $('elGrid');
    var modal = $('elModal');
    var addModal = $('elAddModal');
    var notice = $('elToast');

    if (notice) {
      notice.addEventListener('mouseenter', function () {
        toast._hovering = true;
        clearTimeout(toast._t);
        clearTimeout(toast._hide);
        notice.hidden = false;
        notice.classList.add('is-show');
      });
      notice.addEventListener('mouseleave', function () {
        toast._hovering = false;
        scheduleToastHide();
      });
      var closeBtn = $('elToastClose');
      if (closeBtn) {
        closeBtn.addEventListener('click', function (e) {
          e.preventDefault();
          e.stopPropagation();
          hideToast(true);
        });
      }
    }

    if (search) {
      search.addEventListener('input', renderGrid);
      search.addEventListener('keydown', function (e) {
        if (e.key === 'Escape') search.blur();
      });
    }
    if (clearBtn) {
      clearBtn.addEventListener('click', function () {
        if (search) search.value = '';
        selectedId = null;
        renderGrid();
        if (search) search.focus();
      });
    }
    if (company) company.addEventListener('change', renderGrid);
    if (grid) {
      grid.addEventListener('click', function (e) {
        var btn = e.target.closest && e.target.closest('[data-emp-open]');
        if (!btn) return;
        openModal(findEmp(btn.getAttribute('data-emp-open')));
      });
    }
    if (modal) {
      modal.addEventListener('click', function (e) {
        if (e.target && e.target.classList && e.target.classList.contains('el-modal-backdrop')) {
          if (modalPane !== 'view') showModalPane('view');
          else closeModal();
          return;
        }
        if (e.target && e.target.hasAttribute && e.target.hasAttribute('data-close-el-modal')) {
          closeModal();
        }
      });
    }
    $('elEditBtn') &&
      $('elEditBtn').addEventListener('click', function () {
        fillEditForm(currentEmp);
        showModalPane('edit');
        setTimeout(function () {
          $('elEditName') && $('elEditName').focus();
        }, 50);
      });
    $('elEditCancel') &&
      $('elEditCancel').addEventListener('click', function () {
        showModalPane('view');
      });
    $('elEditForm') &&
      $('elEditForm').addEventListener('submit', function (e) {
        e.preventDefault();
        submitEditEmployee().catch(function (err) {
          showImportResult(err.message, true);
        });
      });
    $('elDeleteBtn') &&
      $('elDeleteBtn').addEventListener('click', function () {
        showModalPane('delete');
      });
    $('elDeleteCancel') &&
      $('elDeleteCancel').addEventListener('click', function () {
        showModalPane('view');
      });
    $('elDeleteConfirm') &&
      $('elDeleteConfirm').addEventListener('click', function () {
        confirmDeleteEmployee().catch(function (err) {
          showImportResult(err.message, true);
        });
      });
    $('elAddEmpBtn') && $('elAddEmpBtn').addEventListener('click', openAddModal);
    if (addModal) {
      addModal.addEventListener('click', function (e) {
        if (e.target && e.target.hasAttribute && e.target.hasAttribute('data-close-el-add')) {
          closeAddModal();
        }
      });
    }
    $('elAddForm') &&
      $('elAddForm').addEventListener('submit', function (e) {
        e.preventDefault();
        submitNewEmployee().catch(function (err) {
          showImportResult(err.message, true);
          $('elAddEmpId') && $('elAddEmpId').focus();
        });
      });
    $('elTemplateBtn') &&
      $('elTemplateBtn').addEventListener('click', function () {
        downloadBlob('/hr/api/employee-list/template', 'employee_list_template.xlsx').catch(function (err) {
          showImportResult(err.message, true);
        });
      });
    $('elExportBtn') &&
      $('elExportBtn').addEventListener('click', function () {
        downloadBlob('/hr/api/employee-list/export', 'employee_list.xlsx').catch(function (err) {
          showImportResult(err.message, true);
        });
      });
    $('elImportBtn') &&
      $('elImportBtn').addEventListener('click', function () {
        $('elImportFile') && $('elImportFile').click();
      });
    $('elImportFile') &&
      $('elImportFile').addEventListener('change', function () {
        if (this.files && this.files[0]) uploadImport(this.files[0]);
        this.value = '';
      });
    document.addEventListener('keydown', function (e) {
      if (e.key !== 'Escape') return;
      if (addModal && !addModal.hidden) {
        closeAddModal();
        return;
      }
      if (modal && !modal.hidden && modalPane !== 'view') {
        showModalPane('view');
        return;
      }
      closeModal();
    });
  }

  document.addEventListener('DOMContentLoaded', function () {
    if (!localStorage.getItem('access_token') && !localStorage.getItem('token')) {
      window.location.href = '/login';
      return;
    }
    bind();
    loadEmployees();
  });
})();
