# MMR: Chargeable vs Non-Chargeable rules

This document describes how the **Report Generation** module assigns **Chargeable** or **Non-Chargeable** to each work order for the **Space** column (and for all dashboards, Excel reports, and email summaries that use the same logic).

**Implementation:** `module_mmr/mmr_service.py` — function `_resolve_chargeable()` (and helpers it calls).

**Outputs:** Every row is normalised to exactly one of:

| Value             | Meaning (for reporting / pie charts / email tables) |
|-------------------|-----------------------------------------------------|
| **Chargeable**    | Counted as chargeable in analysis                   |
| **Non-Chargeable**| Counted as non-chargeable in analysis               |

---

## 1. Order of evaluation

Rules are checked **in order**; the **first** rule that applies **wins**. Later rules are not evaluated for that row.

---

## 2. Global rules (Service Group & project)

These apply **before** any BaseUnit or Excel Space logic.

### 2.1 Non-Chargeable — Facade Cleaning

| Condition | Result |
|-----------|--------|
| **Service Group** (lowercased) contains the phrase `facade cleaning` | **Non-Chargeable** |

---

### 2.2 Non-Chargeable — Elevator works

| Condition | Result |
|-----------|--------|
| **Service Group** matches **elevator** or **elevater** (regex `elevat(or|er)`, case-insensitive) | **Non-Chargeable** |

**Examples:** “Elevator system”, CAFM typo “Elevater system”.  
**Not matched:** unrelated words like “elevation” (civil).

---

### 2.3 Non-Chargeable — Garden City, AC/HVAC only

| Condition | Result |
|-----------|--------|
| **Client** or **Contract** (combined, lowercased) contains `garden` **and** **Service Group** looks like AC/HVAC: contains `hvac`, or `ac`, or `air conditioning`, or `airconditioning` | **Non-Chargeable** |

Other Garden City service groups are **not** forced non-chargeable by this rule alone.

---

## 3. BaseUnit rules (when BaseUnit has text)

After sections 2.1–2.3, if **BaseUnit** is **not** empty (after trim):

### 3.1 Non-Chargeable — specific CAFM BaseUnit labels only

BaseUnit is compared **case-insensitively**. It is **Non-Chargeable** if **any** of the following hold:

| Pattern | Notes |
|---------|--------|
| Contains **reception** | e.g. `Reception` |
| Contains **outside** **or** **out side** | e.g. `Outside area`, `Out side area` |
| Contains both **exit** and **entry** | e.g. `Exit/ Entry` |
| Contains **exit/** **or** **exit /** | e.g. `Exit/ lobby` |

### 3.2 Chargeable — any other non-empty BaseUnit

If BaseUnit has text and **does not** match section 3.1:

| Result |
|--------|
| **Chargeable** |

**Examples (Chargeable):** `Apt No 911`, `Lobby`, `Lift Area`, `GYM Equipment`, numeric-only labels, etc.  
This applies to **all** clients, including **Askaan**, **Ajman Holding**, and **Injaaz**, when BaseUnit is non-empty and not in 3.1.

---

## 4. Empty BaseUnit — office clients, then Excel Space

When **BaseUnit** is **empty** (after trim):

### 4.1 Chargeable — named office / internal clients

| Condition | Result |
|-----------|--------|
| **Client** or **Contract** (combined, lowercased) contains **askaan**, **ajman holding**, or **injaaz** | **Chargeable** |

Used when CAFM leaves BaseUnit blank for those sites.

---

### 4.2 Otherwise — use Excel **Space** column

If the row is **not** in section 4.1:

1. Read the workbook **Space** cell.
2. Normalize known typos (see section 5).
3. If the normalised value is **Chargeable** or **Non-Chargeable**, use it.
4. If missing, unknown, or anything else → **Non-Chargeable**.

---

## 5. Excel Space typo normalisation

When the Excel **Space** value is used (empty BaseUnit, non–4.1 clients), these spellings are mapped:

| Raw (case-insensitive examples) | Mapped to |
|----------------------------------|-----------|
| `chargeable`, `chargebale` | **Chargeable** |
| `non-chargeable`, `non-chargebale`, `non chargeable`, `non chargebale` | **Non-Chargeable** |

Other values are not trusted as chargeable flags unless they resolve to the two canonical labels above.

---

## 6. Where this logic is applied

The same resolution is used when:

- Uploading a CAFM Excel file to the MMR dashboard  
- Opening a saved report from the report folder  
- Building the **Space** column in generated Excel reports  
- **Chargeable** summaries in scheduled / manual emails  
- Dashboard KPIs and charts that use “resolved” chargeable totals  

The **Service Group** and **BaseUnit** columns from the CAFM extract drive most rows; **Client**, **Contract**, and **Space** are also inputs as described above.

---

## 7. Quick reference card

| Situation | Typical result |
|-----------|----------------|
| Facade Cleaning (service group) | Non-Chargeable |
| Elevator / Elevater (service group) | Non-Chargeable |
| Garden + AC/HVAC-type service group | Non-Chargeable |
| BaseUnit = reception / outside / out side / exit+entry / exit/ | Non-Chargeable |
| BaseUnit = anything else (non-empty) | Chargeable |
| BaseUnit empty + Askaan / Ajman Holding / Injaaz | Chargeable |
| BaseUnit empty + other client + Excel Space chargeable | Chargeable |
| BaseUnit empty + other client + Excel Space non-chargeable or blank | Non-Chargeable |

---

## 8. Maintenance note

If business rules change, update **`_resolve_chargeable`** (and related helpers such as `_baseunit_is_non_chargeable_cafm_labels`) in **`mmr_service.py`**, then revise this document so they stay in sync.

**Last documented logic:** matches `module_mmr/mmr_service.py` as maintained in-repo (see git history for precise dates of rule changes).
