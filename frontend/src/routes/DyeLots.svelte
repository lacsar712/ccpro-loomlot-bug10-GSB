<script>
  import { onMount } from 'svelte';
  import { api, VAT_STATUS, toLocalInput, fromLocalInput } from '../lib/api.js';

  let allVats = [];
  let openableVats = [];
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

  async function loadLotsOnly() {
    rows = await api('/dye-lots');
  }

  async function load() {
    error = '';
    try {
      // 每次进入/提交后都重新拉取：
      // - /vats 全量仅用于表格中染缸名称展示（含已排液缸）
      // - /vats?openable=true 与后端开立拦截同源，专用于下拉可选集合
      // 不再做「只拉一次」缓存，排液后下拉与徽章即时一致，刷新前后不变。
      const [all, openable] = await Promise.all([api('/vats'), api('/vats?openable=true')]);
      allVats = all;
      openableVats = openable;
      await loadLotsOnly();
      const stillSelectable = openableVats.some((v) => String(v.id) === form.vatId);
      if (!stillSelectable) {
        form.vatId = openableVats.length ? String(openableVats[0].id) : '';
      }
    } catch (e) {
      error = e.message;
    }
  }

  onMount(load);

  function vatLabel(id) {
    const v = allVats.find((x) => x.id === id);
    if (!v) return id;
    return `${v.vatCode}（${VAT_STATUS[v.status] || v.status}）`;
  }

  // 编辑中的染程若其当前染缸已排液：如实展示但禁用，不可被重新选中。
  // 可选集合始终等于 openableVats（与后端同源），多出来的这一项不可选。
  $: editingVat = editing ? allVats.find((v) => v.id === Number(form.vatId)) : null;
  $: currentVatDrained =
    !!editingVat && !openableVats.some((v) => v.id === editingVat.id);

  async function save() {
    error = '';
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
      <select bind:value={form.vatId} disabled={!openableVats.length && !currentVatDrained}>
        {#if currentVatDrained && editingVat}
          <option value={String(editingVat.id)} disabled
            >{editingVat.vatCode} · {VAT_STATUS[editingVat.status] || editingVat.status}（已排液，不可开立）</option
          >
        {/if}
        {#each openableVats as v}
          <option value={String(v.id)}
            >{v.vatCode} · {VAT_STATUS[v.status] || v.status} · {v.fiberType}</option
          >
        {:else}
          {#if !currentVatDrained}
            <option value="">暂无可开立染缸</option>
          {/if}
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
      <button class="btn ghost" type="button" on:click={() => (editing = null)}>取消</button>
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
