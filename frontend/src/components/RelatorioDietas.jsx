import { useEffect, useState } from 'react'
import { api } from '../services/api.js'
import { MARCA } from '../services/marca.js'
import { BOTAO } from './Operacao.jsx'

const CAMPO = 'mt-1 min-h-11 w-full min-w-0 rounded-lg border border-slate-300 bg-white px-3 text-base font-normal'
const SITUACOES = { PENDENTE: 'Pendente', EM_PREPARO: 'Em preparo', PRONTO: 'Pronto', ENTREGUE: 'Entregue', CANCELADO: 'Cancelado' }
const ACOES = { SOLICITADO: 'Solicitação registrada', PEDIDO_CORRIGIDO: 'Pedido corrigido', ETAPA_ALTERADA: 'Etapa alterada',
  ENTREGA_COMPROVADA_NUTRICAO: 'Entrega comprovada pela Nutrição', ENTREGA_REGISTRADA: 'Entrega registrada', ENTREGA_CONFIRMADA_QR: 'Recebimento confirmado por QR Code',
  VINCULO_CONFERIDO: 'Vínculo com prescrição conferido', RETIRADA_REGISTRADA: 'Retirada registrada', COPEIRA_IDENTIFICADA_QR: 'Copeira identificada pelo QR Code' }
const FORMATOS = { xlsx: 'Excel (.xlsx)', ods: 'LibreOffice Calc (.ods)', csv: 'Google Sheets (.csv)' }
const horario = (data) => data ? new Date(data).toLocaleString('pt-BR', { timeZone: 'America/Sao_Paulo' }) : '—'

function diaAtual() {
  const partes = new Intl.DateTimeFormat('en-CA', { timeZone: 'America/Sao_Paulo', year: 'numeric', month: '2-digit', day: '2-digit' }).formatToParts(new Date())
  return ['year', 'month', 'day'].map((tipo) => partes.find((p) => p.type === tipo).value).join('-')
}

function filtrosIniciais(filialId) {
  const hoje = diaAtual()
  return { inicio: `${hoje}T00:00`, fim: `${hoje}T23:59`, filial_id: filialId ? String(filialId) : '', data_base: 'solicitacao', tipo_solicitacao: '', status: '' }
}

function parametros(filtros) {
  return { inicio: `${filtros.inicio}:00-03:00`, fim: `${filtros.fim}:59.999999-03:00`, data_base: filtros.data_base,
    ...(filtros.filial_id && { filial_id: Number(filtros.filial_id) }), ...(filtros.tipo_solicitacao && { tipo_solicitacao: filtros.tipo_solicitacao }), ...(filtros.status && { status: filtros.status }) }
}

export default function RelatorioDietas({ filialId, filiais, consolidado = false }) {
  const endpoint = consolidado ? '/relatorios/rede' : '/relatorios/dietas-periodo'
  const [filtros, setFiltros] = useState(() => filtrosIniciais(filialId))
  const [consulta, setConsulta] = useState(() => ({ filtros: filtrosIniciais(filialId), pagina: 1, versao: 0 }))
  const [resultado, setResultado] = useState(null)
  const [carregando, setCarregando] = useState(true)
  const [erro, setErro] = useState('')
  const [formato, setFormato] = useState('xlsx')
  const [exportando, setExportando] = useState(false)
  const [mensagem, setMensagem] = useState('')
  const [foto, setFoto] = useState(null)
  const [historico, setHistorico] = useState(null)
  useEffect(() => () => { if (foto?.url) URL.revokeObjectURL(foto.url) }, [foto])
  const alterados = JSON.stringify(filtros) !== JSON.stringify(consulta.filtros)

  useEffect(() => {
    const controller = new AbortController()
    const inicio = setTimeout(async () => {
      setCarregando(true); setErro(''); setResultado(null); setMensagem('')
      try {
        const { data } = await api.get(endpoint, { params: { ...parametros(consulta.filtros), pagina: consulta.pagina }, signal: controller.signal })
        if (!controller.signal.aborted) setResultado(data)
      } catch (e) {
        if (!controller.signal.aborted) setErro(typeof e.response?.data?.detail === 'string' ? e.response.data.detail : 'Não foi possível carregar o relatório de dietas')
      } finally { if (!controller.signal.aborted) setCarregando(false) }
    }, 0)
    return () => { clearTimeout(inicio); controller.abort() }
  }, [consulta, endpoint])

  function alterar(chave, valor) { setFiltros((atual) => ({ ...atual, [chave]: valor })) }

  function consultar(evento) {
    evento.preventDefault()
    if (filtros.inicio > filtros.fim) { setErro('A data e hora inicial devem ser anteriores ou iguais às finais'); return }
    setConsulta((atual) => ({ filtros: { ...filtros }, pagina: 1, versao: atual.versao + 1 }))
  }

  async function exportar() {
    if (exportando || carregando || alterados || !resultado) return
    setExportando(true); setErro(''); setMensagem('')
    try {
      const resposta = await api.get(`${endpoint}/exportar`, { params: { ...parametros(consulta.filtros), formato }, responseType: 'blob' })
      const url = URL.createObjectURL(resposta.data)
      const link = document.createElement('a')
      link.href = url
      link.download = resposta.headers['content-disposition']?.match(/filename="([^"]+)"/)?.[1] || `${MARCA.prefixoArquivos}-dietas.${formato}`
      document.body.appendChild(link); link.click(); link.remove()
      setTimeout(() => URL.revokeObjectURL(url), 1000)
      setMensagem(formato === 'csv' ? 'CSV baixado. No Google Sheets, use Arquivo → Importar para abrir o relatório.' : `Relatório baixado para ${formato === 'xlsx' ? 'Excel' : 'LibreOffice Calc'}.`)
    } catch (e) {
      let dados = e.response?.data
      if (dados instanceof Blob) { try { dados = JSON.parse(await dados.text()) } catch { dados = null } }
      setErro(typeof dados?.detail === 'string' ? dados.detail : 'Não foi possível exportar o relatório. Tente novamente')
    } finally { setExportando(false) }
  }

  async function abrirComprovante(item) {
    try {
      const { data } = await api.get(`/relatorios/rede/${item.servidor_id}/pedidos/${item.pedido_uuid}/comprovante`, { responseType: 'blob' })
      setFoto({ url: URL.createObjectURL(data), titulo: `Comprovante · ${item.unidade} · Pedido #${item.pedido_id}` })
    } catch { setErro('Não foi possível abrir o comprovante. Atualize o relatório e confira a sincronização da foto.') }
  }

  async function abrirHistorico(item) {
    try {
      const { data } = await api.get(`/relatorios/rede/${item.servidor_id}/pedidos/${item.pedido_uuid}/historico`)
      setHistorico({ ...data, titulo: `${item.unidade} · Pedido #${item.pedido_id}` })
    } catch { setErro('Não foi possível consultar o histórico da unidade.') }
  }

  return <section className="min-w-0 space-y-4 rounded-xl bg-panel p-4 sm:p-5 md:col-span-3" aria-labelledby="titulo-relatorio-dietas">
    <div><h2 id="titulo-relatorio-dietas" className="text-xl font-bold">Relatório de dietas e solicitações</h2><p className="mt-1 text-sm text-slate-700">Todas as dietas e refeições médicas no período escolhido. Datas e horários de Brasília.</p></div>
    {consolidado && <p className="rounded-lg bg-brand-soft p-3 text-sm text-brand-ink">Visão consolidada da rede. Os registros das unidades refletem a última sincronização recebida. Durante uma interrupção, novos atendimentos continuam armazenados localmente.</p>}
    <form onSubmit={consultar} className="grid min-w-0 grid-cols-1 items-end gap-3 sm:grid-cols-2 xl:grid-cols-3">
      {filiais && <label className="min-w-0 text-sm font-semibold">Unidade<select className={CAMPO} value={filtros.filial_id} onChange={(e) => alterar('filial_id', e.target.value)}>
        <option value="">Todas as unidades</option>{filiais.map((f) => <option key={f.id} value={f.id}>{f.nome} ({f.codigo_slug}){f.ativa ? '' : ' (Inativa)'}</option>)}
      </select></label>}
      <label className="min-w-0 text-sm font-semibold">Data e hora inicial<input type="datetime-local" required step="60" value={filtros.inicio} onChange={(e) => alterar('inicio', e.target.value)} className={CAMPO} /></label>
      <label className="min-w-0 text-sm font-semibold">Data e hora final<input type="datetime-local" required step="60" value={filtros.fim} onChange={(e) => alterar('fim', e.target.value)} className={CAMPO} /></label>
      <label className="min-w-0 text-sm font-semibold">Período baseado em<select className={CAMPO} value={filtros.data_base} onChange={(e) => alterar('data_base', e.target.value)}><option value="solicitacao">Data da solicitação</option><option value="entrega">Data da entrega</option></select></label>
      <label className="min-w-0 text-sm font-semibold">Formulário<select className={CAMPO} value={filtros.tipo_solicitacao} onChange={(e) => alterar('tipo_solicitacao', e.target.value)}><option value="">Todos</option><option value="PACIENTE">Enfermagem</option><option value="MEDICO">Médico</option></select></label>
      <label className="min-w-0 text-sm font-semibold">Situação<select className={CAMPO} value={filtros.status} onChange={(e) => alterar('status', e.target.value)}><option value="">Todas</option>{Object.entries(SITUACOES).map(([id, nome]) => <option key={id} value={id}>{nome}</option>)}</select></label>
      <button className={`${BOTAO} bg-brand text-white`}>Consultar dietas</button>
    </form>
    {alterados && <p role="status" className="rounded-lg bg-amber-50 p-3 text-sm text-amber-950">Filtros alterados. Clique em Consultar dietas para atualizar o resultado e a exportação.</p>}
    <div className="grid items-end gap-3 rounded-lg bg-slate-50 p-3 sm:grid-cols-[1fr_auto]">
      <label className="min-w-0 text-sm font-semibold">Abrir relatório em<select className={CAMPO} disabled={exportando} value={formato} onChange={(e) => setFormato(e.target.value)}>{Object.entries(FORMATOS).map(([id, nome]) => <option key={id} value={id}>{nome}</option>)}</select></label>
      <button onClick={exportar} disabled={exportando || carregando || alterados || !resultado} className={`${BOTAO} bg-brand-vibrant text-brand-ink hover:bg-brand-vibrant-hover`}>{exportando ? 'Preparando arquivo…' : 'Exportar relatório'}</button>
      <p className="text-xs text-slate-700 sm:col-span-2">A exportação inclui todos os resultados do filtro, mesmo de outras páginas. Para Google Sheets, baixe o CSV e importe o arquivo.</p>
    </div>
    {erro && <p role="alert" className="rounded-lg bg-red-50 p-3 text-sm text-red-900">{erro}</p>}
    {mensagem && <p role="status" className="rounded-lg bg-emerald-50 p-3 text-sm text-emerald-950">{mensagem}</p>}
    {carregando && <p role="status" className="py-4 text-sm">Carregando dietas…</p>}
    {resultado && <>
      <p className="text-sm text-slate-700">Unidades: {resultado.contexto.unidades.join(', ') || 'Nenhuma disponível'}. Cada registro representa uma solicitação.</p>
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">{[['total', 'Solicitações'], ['entregues', 'Entregues'], ['prontos', 'Prontas'], ['cancelados', 'Canceladas']].map(([chave, titulo]) => <div key={chave} className="rounded-lg bg-slate-50 p-3"><p className="text-sm text-slate-700">{titulo}</p><strong className="text-2xl">{resultado.totais[chave]}</strong></div>)}</div>
      <h3 className="font-bold">Resumo por dieta</h3>
      {!resultado.resumo.length ? <p className="rounded-lg bg-slate-50 p-4 text-sm">Nenhuma solicitação encontrada no período selecionado.</p> : <>
        <div className="overflow-x-auto rounded-lg bg-slate-50"><table className="w-full text-left text-sm"><thead className="bg-slate-100"><tr>{['Unidade', 'Dieta / categoria', 'Total', 'Pendentes', 'Em preparo', 'Prontas', 'Entregues', 'Canceladas'].map((titulo) => <th key={titulo} className="whitespace-nowrap p-3 font-semibold">{titulo}</th>)}</tr></thead><tbody>{resultado.resumo.map((linha) => <tr key={`${linha.unidade_id}:${linha.dieta_id ?? linha.dieta}`} className="border-t border-slate-200"><td className="p-3">{linha.unidade}<span className="mt-1 block text-xs text-slate-600">{linha.unidade_codigo}</span></td><td className="p-3 font-semibold">{linha.dieta}</td>{['total', 'pendentes', 'em_preparo', 'prontos', 'entregues', 'cancelados'].map((chave) => <td key={chave} className="p-3 text-right">{linha[chave]}</td>)}</tr>)}</tbody></table></div>
        <h3 className="font-bold">Solicitações do período</h3>
        <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">{resultado.itens.map((item) => <article key={item.pedido_uuid || item.pedido_id} className="min-w-0 space-y-2 break-words rounded-xl bg-slate-50 p-4 text-sm">
          <div className="flex flex-wrap justify-between gap-2"><strong>Pedido #{item.pedido_id}</strong><span className="rounded bg-slate-200 px-2 py-1">{SITUACOES[item.status] || item.status}</span></div>
          <p className="text-xs text-slate-700">{item.unidade} ({item.unidade_codigo}) · {item.tipo_solicitacao === 'MEDICO' ? 'Médico' : 'Enfermagem'}</p>
          {consolidado && <p className="text-xs text-slate-600">Origem: {item.origem_servidor} · Recebido no central: {horario(item.sincronizado_em)}{item.comprovante_pendente && ' · Foto aguardando sincronização'}</p>}
          <p className="font-bold">{item.destinatario || 'Destinatário não informado'}</p>
          <p><strong>Solicitante:</strong> {item.solicitante_nome || 'Não registrado'}{item.solicitante_identificacao && ` · ${item.solicitante_identificacao}`}</p>
          <p><strong>Dieta:</strong> {item.dieta}</p>{item.refeicao && <p><strong>Refeição:</strong> {item.refeicao}</p>}
          {item.cardapio_acompanhante && <p><strong>Cardápio do acompanhante (GERAL):</strong> {item.cardapio_acompanhante}</p>}
          {item.liquido_espessado && <p><strong>Líquido espessado:</strong> {item.liquido_espessado}{item.tipo_liquido_espessado && ` · ${item.tipo_liquido_espessado}`}</p>}
          {item.status === 'CANCELADO' && <div className="space-y-1 rounded-lg bg-red-50 p-3 text-red-950">
            <p><strong>Cancelado por:</strong> {item.cancelado_por_nome || 'Não registrado na época'}</p>
            <p><strong>Cancelamento:</strong> {horario(item.cancelado_em)}</p>
            <p className="whitespace-pre-wrap"><strong>Motivo:</strong> {item.motivo_cancelamento || 'Não registrado na época'}</p>
          </div>}
          <p className="text-slate-700">Solicitação: {horario(item.criado_em)}</p><p className="text-slate-700">Entrega: {horario(item.entregue_em)}{item.copeira_nome && ` · ${item.copeira_nome}`}</p>
          {item.retirada_em && <div className="space-y-1 rounded-lg bg-brand-soft p-3 text-brand-ink"><p><strong>Copeira responsável:</strong> {item.copeira_nome}</p><p><strong>Identificação da copeira:</strong> {horario(item.retirada_em)}</p>
            {item.etapa_entrega === 'EM_ENTREGA' && <p className="font-semibold">Em entrega · aguardando confirmação do recebedor</p>}</div>}
          {item.registrado_por_nome && <p className="text-slate-700">Entrega registrada por: {item.registrado_por_nome}</p>}
          {item.registrado_em && <p className="text-slate-700">Lançamento no sistema: {horario(item.registrado_em)}</p>}
          {item.comprovante_disponivel && (!consolidado || !item.servidor_id) && <p className="text-slate-700">Foto da filipeta disponível no relatório de entregas.</p>}
          {consolidado && item.servidor_id && <div className="flex flex-wrap gap-2">{item.comprovante_disponivel && <button className="ui-button ui-button-secondary" onClick={() => abrirComprovante(item)}>Ver foto da filipeta</button>}
            <button className="ui-button ui-button-secondary" onClick={() => abrirHistorico(item)}>Ver histórico da unidade</button></div>}
          {(item.recebedor_nome || item.recebedor_registro_profissional) && <p className="text-slate-700">Recebedor: {item.recebedor_nome || 'Nome não registrado'}{item.recebedor_registro_profissional && ` · ${item.recebedor_registro_profissional}`}
            {item.origem_entrega === 'QR Code' ? ' · Confirmado por QR Code' : item.assinatura_registrada ? ' · Assinatura registrada' : ''}</p>}
          {item.prescricao_referencia && <div className="rounded-lg bg-white p-3"><p><strong>Prescrição:</strong> {item.prescricao_referencia} · {horario(item.prescricao_data_hora)}</p>
            <p>{item.prescritor_nome} · {item.prescritor_registro}</p><p>Vínculo: {item.prescricao_situacao === 'CONFERIDA' ? `conferido por ${item.conferencia_nome}` : 'informado pelo solicitante'}</p></div>}
        </article>)}</div>
        <nav aria-label="Páginas do relatório de dietas" className="flex flex-wrap items-center justify-between gap-2">
          <button onClick={() => setConsulta((atual) => ({ ...atual, pagina: atual.pagina - 1 }))} disabled={resultado.pagina <= 1} className={`${BOTAO} bg-slate-50`}>Anterior</button><span className="text-sm">Página {resultado.pagina} de {resultado.total_paginas}</span><button onClick={() => setConsulta((atual) => ({ ...atual, pagina: atual.pagina + 1 }))} disabled={resultado.pagina >= resultado.total_paginas} className={`${BOTAO} bg-slate-50`}>Próxima</button>
        </nav>
      </>}
    </>}
    {foto && <div className="fixed inset-0 z-50 grid place-items-center overflow-auto bg-slate-950/60 p-4" role="dialog" aria-modal="true" aria-label={foto.titulo}><div className="max-w-3xl space-y-3 rounded-xl bg-white p-4"><div className="flex items-center justify-between gap-3"><h3 className="font-bold">{foto.titulo}</h3><button className="ui-button ui-button-secondary" onClick={() => setFoto(null)}>Fechar foto</button></div><img src={foto.url} alt="Foto da filipeta de comprovação da entrega" className="max-h-[75vh] max-w-full object-contain" /></div></div>}
    {historico && <div className="fixed inset-0 z-50 grid place-items-center overflow-auto bg-slate-950/60 p-4" role="dialog" aria-modal="true" aria-label="Histórico da unidade"><section className="max-h-[85vh] w-full max-w-2xl space-y-3 overflow-auto rounded-xl bg-white p-5"><div className="flex items-center justify-between gap-3"><h3 className="font-bold">{historico.titulo}</h3><button className="ui-button ui-button-secondary" onClick={() => setHistorico(null)}>Fechar histórico</button></div>
      {historico.historico?.map((h, i) => <p key={i} className="rounded-lg bg-slate-50 p-3 text-sm">{horario(h.data_hora)} · {SITUACOES[h.status_anterior] || h.status_anterior || 'Início'} → {SITUACOES[h.status_novo] || h.status_novo} · {h.autor_nome || 'Operação da unidade'}</p>)}
      {historico.eventos?.map((e, i) => <p key={i} className="rounded-lg bg-brand-soft p-3 text-sm">{horario(e.criado_em)} · {ACOES[e.acao] || 'Evento registrado'} · {e.autor_nome || 'Operação da unidade'}{e.motivo && ` · ${e.motivo}`}</p>)}
      {!historico.historico?.length && !historico.eventos?.length && <p>Não há eventos registrados nesta publicação.</p>}</section></div>}
  </section>
}
