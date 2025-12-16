// Simple helper to populate assetSelect, systemSelect, descriptionSelect
// Expects /hvac-mep/dropdowns to return JSON with the shape of dropdown_data.json

(function () {
  async function fetchDropdownData() {
    try {
      const res = await fetch(window.location.origin + '/hvac-mep/dropdowns');
      if (!res.ok) throw new Error('Failed to load dropdown data');
      return await res.json();
    } catch (err) {
      console.error('Dropdown load error:', err);
      return null;
    }
  }

  function clearSelect(selectEl) {
    selectEl.innerHTML = '';
    const opt = document.createElement('option');
    opt.value = '';
    opt.textContent = '-- Select --';
    selectEl.appendChild(opt);
    selectEl.disabled = true;
  }

  function populateSelect(selectEl, items) {
    clearSelect(selectEl);
    if (!items || items.length === 0) return;
    selectEl.disabled = false;
    items.forEach(it => {
      const opt = document.createElement('option');
      opt.value = it;
      opt.textContent = it;
      selectEl.appendChild(opt);
    });
  }

  async function init() {
    const data = await fetchDropdownData();
    if (!data) return;

    // Flatten top-level categories into the assetSelect group list
    const assetSelect = document.getElementById('assetSelect');
    const systemSelect = document.getElementById('systemSelect');
    const descriptionSelect = document.getElementById('descriptionSelect');

    if (!assetSelect || !systemSelect || !descriptionSelect) return;

    // Build a grouped list of asset categories for assetSelect
    clearSelect(assetSelect);
    // Insert a grouped label option set: we'll set option value to "Category|SubKey" when needed,
    // but for simplicity we will fill assetSelect with "Category - SubKey" strings where appropriate.
    let topOptions = [];
    Object.keys(data).forEach(category => {
      const subgroups = data[category];
      // If category contains multiple subgroup keys, add subgroup labels
      if (subgroups && typeof subgroups === 'object') {
        Object.keys(subgroups).forEach(subkey => {
          topOptions.push({ value: `${category}||${subkey}`, label: `${category} — ${subkey}`});
        });
      } else {
        // fallback: category itself
        topOptions.push({ value: category, label: category });
      }
    });

    topOptions.forEach(o => {
      const opt = document.createElement('option');
      opt.value = o.value;
      opt.textContent = o.label;
      assetSelect.appendChild(opt);
    });

    // When an asset is chosen, set systems and descriptions
    assetSelect.addEventListener('change', function () {
      const val = this.value; // format "Category||Subkey"
      clearSelect(systemSelect);
      clearSelect(descriptionSelect);

      if (!val) return;

      const [category, subkey] = val.split('||');
      const systemsObj = data[category] && data[category][subkey];
      if (Array.isArray(systemsObj)) {
        // systemsObj currently is array of system labels; we consider that "system" level
        populateSelect(systemSelect, systemsObj);
      } else if (systemsObj && typeof systemsObj === 'object') {
        // If systemsObj is an object with keys being systems and values descriptions_by_system
        populateSelect(systemSelect, Object.keys(systemsObj));
      } else {
        // No systems found, leave selects disabled
      }
    });

    // When system changes, attempt to populate descriptions
    systemSelect.addEventListener('change', function () {
      const aVal = assetSelect.value;
      if (!aVal) return;
      const [category, subkey] = aVal.split('||');
      const systemsObj = data[category] && data[category][subkey];
      let descriptions = [];
      if (Array.isArray(systemsObj)) {
        // systemsObj is systems array, so descriptions not provided here. Keep description empty.
        descriptions = [];
      } else if (systemsObj && typeof systemsObj === 'object') {
        const chosenSystem = this.value;
        const maybe = systemsObj[chosenSystem];
        if (Array.isArray(maybe)) descriptions = maybe;
      }
      populateSelect(descriptionSelect, descriptions);
    });

    // Enable initial selects
    clearSelect(systemSelect);
    clearSelect(descriptionSelect);
    assetSelect.disabled = false;
  }

  // Initialize on DOM ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();