<script>
  import { onMount } from 'svelte';
  import { api, VAT_STATUS, toLocalInput, fromLocalInput } from '../lib/api.js';

  let vats = [];
  let rows = [];
  let error = '';
  let form = {
    vatId: '',
    recipeName: '',
    fabricKg: 20,
    startedAt: toLocalInput(new Date().toISOString()),
    operatorName: '染程操作员',
  };
  let editing = null;
  let editingVatId = null;

  // 下拉候选 = 后端按统一判定下发的 openable 染缸；编辑时额外保留本条染程
  // 当前所在缸（可能已排液，禁用展示，不可移缸过去）。
  $: selectVats = vats.filter(
    (v) => v.openable || (editing !== null && String(v.id) === String(form.vatId))
  );

  async function loadLotsOnly() {
    rows = await api('/dye-lots');
  }

  async function load() {
    error = '';
    try {
      // 每次进入/提交后都重拉染缸，下拉集合始终以后端最新状态为准。
      vats = await api('/vats');
      await loadLotsOnly();
      if (editing === null) {
        const stillSelectable = vats.some(
          (v) => v.openable && String(v.id) === String(form.vatId)
        );
        if (!form.vatId || !stillSelectable) {
          const first = vats.find((v) => v.openable);
          form.vatId = first ? String(first.id) : '';
        }
      }
    } catch (e) {
      error = e.message;
    }
  }

  onMount(load);

  function vatLabel(id) {
    const v = vats.find((x) => x.id === id);
    if (!v) return id;
    return `${v.vatCode}（${VAT_STATUS[v.status] || v.status}）`;
  }

  async function save() {
    error = '';
    const selected = vats.find((v) => String(v.id) === String(form.vatId));
    // 前端拦截与后端同源：仅 openable 可开立/移缸；编辑且不换缸时放行。
    const staysOnSameVat = editing !== null && selected && selected.id === editingVatId;
    if (!selected || (!selected.openable && !staysOnSameVat)) {
      error = '该染缸已排液，不可开立或移入染程';
      return;
    }
    try {
      const body = {
        vatId: Number(form.vatId),
        recipeName: form.recipeName.trim(),
        fabricKg: Number(form.fabricKg),
        startedAt: fromLocalInput(form.startedAt),
        operatorName: form.operatorName.trim(),
      };
      if (editing) {
        await api(`/dye-lots/${editing}`, { method: 'PUT', body: JSON.stringify(body) });
      } else {
        await api('/dye-lots', { method: 'POST', body: JSON.stringify(body) });
      }
      editing = null;
      editingVatId = null;
      form = {
        ...form,
        recipeName: '',
        fabricKg: 20,
        startedAt: toLocalInput(new Date().toISOString()),
      };
      await load();
    } catch (e) {
      error = e.message;
    }
  }

  function startEdit(row) {
    editing = row.id;
    editingVatId = row.vatId;
    form = {
      vatId: String(row.vatId),
      recipeName: row.recipeName,
      fabricKg: row.fabricKg,
      startedAt: toLocalInput(row.startedAt),
      operatorName: row.operatorName,
    };
  }

  async function remove(id) {
    if (!confirm('确认删除该染程？')) return;
    error = '';
    try {
      await api(`/dye-lots/${id}`, { method: 'DELETE' });
      await loadLotsOnly();
    } catch (e) {
      error = e.message;
    }
  }
</script>

<h1 class="page-title">染程</h1>
<p class="page-sub">仅 ready / dyeing 染缸可开缸；提交后染缸自动变为染色中。</p>

<div class="panel" style="margin-bottom:1rem;">
  <div class="form-grid">
    <label
      >染缸
      <select bind:value={form.vatId}>
        {#if !selectVats.length}
          <option value="">暂无可开缸染缸</option>
        {/if}
        {#each selectVats as v}
          <option value={String(v.id)} disabled={!v.openable}
            >{v.vatCode} · {VAT_STATUS[v.status] || v.status} · {v.fiberType}{v.openable
              ? ''
              : '（已排液，不可开缸）'}</option
          >
        {/each}
      </select>
    </label>
    <label>配方名 <input bind:value={form.recipeName} /></label>
    <label>布料 kg <input type="number" step="0.1" bind:value={form.fabricKg} /></label>
    <label>开始时间 <input type="datetime-local" bind:value={form.startedAt} /></label>
    <label>操作员 <input bind:value={form.operatorName} /></label>
  </div>
  <div class="toolbar">
    <button class="btn" type="button" on:click={save}>{editing ? '保存修改' : '新建染程'}</button>
    {#if editing}
      <button
        class="btn ghost"
        type="button"
        on:click={() => {
          editing = null;
          editingVatId = null;
          load();
        }}>取消</button
      >
    {/if}
  </div>
  {#if error}<p class="err">{error}</p>{/if}
</div>

<div class="panel">
  <table>
    <thead>
      <tr>
        <th>ID</th>
        <th>染缸</th>
        <th>配方</th>
        <th>布料 kg</th>
        <th>开始</th>
        <th>操作员</th>
        <th></th>
      </tr>
    </thead>
    <tbody>
      {#each rows as row}
        <tr>
          <td>{row.id}</td>
          <td>{vatLabel(row.vatId)}</td>
          <td>{row.recipeName}</td>
          <td>{row.fabricKg}</td>
          <td>{new Date(row.startedAt).toLocaleString()}</td>
          <td>{row.operatorName}</td>
          <td class="row-actions">
            <button class="btn ghost small" type="button" on:click={() => startEdit(row)}>编辑</button>
            <button class="btn danger small" type="button" on:click={() => remove(row.id)}>删除</button>
          </td>
        </tr>
      {/each}
    </tbody>
  </table>
</div>
