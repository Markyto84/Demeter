import { useCallback, useEffect, useState } from 'react'
import { api } from '../services/api.js'
import CadastrosUnidade from './CadastrosUnidade.jsx'

const CAMPO = 'mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2'
const hora = valor => valor ? new Date(valor).toLocaleString('pt-BR') : 'Ainda não recebido'
const erroTexto = e => typeof e.response?.data?.detail === 'string' ? e.response.data.detail : 'Não foi possível concluir a operação. Confira os dados e tente novamente.'
function baixar(vinculo) {
  const url = URL.createObjectURL(new Blob([JSON.stringify(vinculo, null, 2)], { type: 'application/json' }))
  const link = document.createElement('a'); link.href = url; link.download = `demeter-vinculo-${vinculo.servidor_id}.json`
  link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000)
}

export default function ServidoresUnidades({ filiais, EditorFormulario }) {
  const [estado, setEstado] = useState(null)
  const [servidores, setServidores] = useState([])
  const [dados, setDados] = useState({ filial_id: '', url_local: '', intervalo_segundos: 60 })
  const [erro, setErro] = useState('')
  const [sucesso, setSucesso] = useState('')
  const [vinculo, setVinculo] = useState(null)
  const [acao, setAcao] = useState(null)
  const [motivo, setMotivo] = useState('')
  const [ocupado, setOcupado] = useState(false)
  const [selecionado, setSelecionado] = useState(null)
  const carregar = useCallback(async () => {
    try {
      const atual = (await api.get('/rede/estado')).data; setEstado(atual)
      if (atual.modo === 'CENTRAL') setServidores((await api.get('/admin/servidores-unidades')).data)
    } catch (e) { setErro(erroTexto(e)) }
  }, [])
  useEffect(() => { Promise.resolve().then(carregar); const timer = setInterval(carregar, 60000); return () => clearInterval(timer) }, [carregar])
  async function criar(e) {
    e.preventDefault(); setOcupado(true); setErro(''); setSucesso(''); setVinculo(null)
    try { const resposta = await api.post('/admin/servidores-unidades', { ...dados, filial_id: Number(dados.filial_id) }); setVinculo(resposta.data.vinculo); await carregar() }
    catch (e) { setErro(erroTexto(e)) } finally { setOcupado(false) }
  }
  async function executar(e) {
    e.preventDefault(); setOcupado(true); setErro(''); setSucesso('')
    try {
      const caminho = acao.tipo === 'ativar' ? 'ativar' : `credencial/${acao.tipo}`
      const resposta = acao.tipo === 'intervalo' ? await api.patch(`/admin/servidores-unidades/${acao.id}`, { motivo, intervalo_segundos: acao.intervalo })
        : await api.post(`/admin/servidores-unidades/${acao.id}/${caminho}`, { motivo })
      if (resposta.data.vinculo) setVinculo(resposta.data.vinculo)
      setSucesso(acao.tipo === 'ativar' ? 'Transferência registrada. Aguarde a confirmação no servidor local antes de abrir os formulários.' : acao.tipo === 'intervalo'
        ? 'Intervalo atualizado. Será recebido no próximo contato da unidade.' : 'Credencial atualizada. A operação continua no servidor da unidade.')
      setAcao(null); setMotivo(''); await carregar()
    } catch (e) { setErro(erroTexto(e)) } finally { setOcupado(false) }
  }
  return <div className="space-y-5">
    <section className="space-y-4 rounded-xl bg-panel p-5"><p className="eyebrow">Continuidade do cuidado</p><h2 className="text-2xl font-bold">Servidores das unidades</h2>
      <p className="max-w-3xl text-sm text-slate-700">A unidade registra e imprime na sua rede local. A central reúne os relatórios e acompanha a sincronização. Alterações de cadastro podem partir das duas equipes.</p>
      <button onClick={carregar} className="ui-button ui-button-secondary">Atualizar situação</button>
      {erro && <p role="alert" className="rounded-lg bg-red-50 p-3 text-red-900">{erro}</p>}{sucesso && <p role="status" className="rounded-lg bg-emerald-50 p-3 text-emerald-950">{sucesso}</p>}
      {!estado ? <p>Carregando servidores…</p> : estado.modo === 'INDEPENDENTE' ? <p className="rounded-lg bg-brand-soft p-4 text-brand-ink">Esta instalação opera de forma independente. A TI poderá definir o papel Central ou Unidade pelo assistente de instalação, durante a implantação.</p>
        : estado.modo === 'UNIDADE' ? <div className="space-y-3"><strong>{estado.operacao_local ? 'Operação local ativada' : 'Preparação · aguardando ativação na central'}</strong><p>Central: {estado.central_disponivel ? 'Conexão recente' : 'Sem contato recente'} · Pedidos aguardando envio: {estado.pedidos_pendentes} · Divergências: {estado.conflitos}</p><p className="text-sm">Último contato: {hora(estado.ultimo_contato)} · Última publicação: {hora(estado.ultima_publicacao)}</p>{estado.ultimo_erro && <p role="status" className="rounded-lg bg-amber-50 p-3 text-amber-950">{estado.ultimo_erro}</p>}
          <button className="ui-button ui-button-secondary" onClick={async () => { try { await api.post('/rede/tentar-novamente'); setSucesso('Nova tentativa agendada, preservando a verificação de integridade.'); await carregar() } catch (e) { setErro(erroTexto(e)) } }}>Agendar nova tentativa</button></div> : null}
    </section>
    {vinculo && <section className="space-y-3 rounded-xl border border-amber-300 bg-amber-50 p-5"><h3 className="font-bold">Vínculo privado pronto</h3><p className="text-sm">Baixe e guarde em local restrito. Ele identifica somente uma instalação. A credencial não ficará disponível para consulta depois que esta tela for fechada.</p><div className="flex gap-2"><button className="ui-button ui-button-primary" onClick={() => baixar(vinculo)}>Baixar vínculo privado</button><button className="ui-button ui-button-secondary" onClick={() => setVinculo(null)}>Fechar vínculo</button></div></section>}
    {estado?.modo === 'CENTRAL' && <>
      <form onSubmit={criar} className="grid gap-4 rounded-xl bg-panel p-5 sm:grid-cols-3"><h3 className="font-bold sm:col-span-3">Preparar servidor local</h3>
        <label className="text-sm font-semibold">Unidade<select className={CAMPO} required value={dados.filial_id} onChange={e => setDados({ ...dados, filial_id: e.target.value })}><option value="">Selecione</option>{filiais.filter(f => f.ativa && !servidores.some(s => s.filial_id === f.id)).map(f => <option key={f.id} value={f.id}>{f.nome}</option>)}</select></label>
        <label className="text-sm font-semibold">Endereço do servidor local<input className={CAMPO} required type="url" placeholder="https://unidade.dominio" value={dados.url_local} onChange={e => setDados({ ...dados, url_local: e.target.value })} /></label>
        <label className="text-sm font-semibold">Intervalo sem pendências (segundos)<input className={CAMPO} required type="number" min={15} max={3600} value={dados.intervalo_segundos} onChange={e => setDados({ ...dados, intervalo_segundos: Number(e.target.value) })} /></label>
        <p className="text-xs text-slate-600 sm:col-span-3">A preparação não transfere os pedidos. Após instalar e homologar o servidor, finalize as filas da unidade no central e ative a operação local.</p><button disabled={ocupado} className="ui-button ui-button-primary sm:col-span-3">Preparar e gerar vínculo</button>
      </form>
      <div className="grid gap-4 xl:grid-cols-2">{servidores.map(s => <article key={s.id} className="space-y-3 rounded-xl bg-panel p-5"><div className="flex flex-wrap items-center justify-between gap-2"><h3 className="text-xl font-bold">{s.unidade}</h3><span className={`rounded-full px-3 py-1 text-sm font-semibold ${s.conectado ? 'bg-emerald-50 text-emerald-900' : 'bg-amber-50 text-amber-900'}`}>{s.conectado ? 'Conexão recente' : 'Sem contato recente'}</span></div>
        <p className="text-sm">{s.operacao_ativada ? 'Atendimento no servidor local' : 'Em preparação'} · Versão {s.versao_aplicacao || 'aguardando'}{!s.credencial_ativa && ' · Vínculo revogado'}</p>
        <dl className="grid grid-cols-2 gap-3 rounded-lg bg-white p-3 text-sm">{[['Pedidos pendentes', s.pedidos_pendentes], ['Divergências', s.conflitos], ['Fotos pendentes', s.fotos_pendentes], ['Espaço livre no servidor', s.espaco_livre_bytes == null ? 'Aguardando' : `${(s.espaco_livre_bytes / 1073741824).toFixed(1)} GB`]].map(([titulo, valor]) => <div key={titulo}><dt className="text-slate-600">{titulo}</dt><dd className="text-lg font-bold">{valor}</dd></div>)}</dl>
        <p className="text-xs text-slate-600">Contato: {hora(s.ultimo_contato)}<br />Publicação: {hora(s.ultima_publicacao)}<br />Intervalo sem pendências: {s.intervalo_segundos} segundos</p>
        <a href={`${s.url_local}/admin`} target="_blank" rel="noreferrer" className="block break-all text-sm font-semibold text-brand underline">Abrir servidor da unidade</a>
        <div className="flex flex-wrap gap-2"><button className="ui-button ui-button-secondary" onClick={() => setSelecionado(s.id)}>Cadastros da unidade</button>{!s.operacao_ativada && <button className="ui-button ui-button-primary" onClick={() => setAcao({ id: s.id, tipo: 'ativar', unidade: s.unidade })}>Ativar operação local</button>}
          <button className="ui-button ui-button-secondary" onClick={() => setAcao({ id: s.id, tipo: 'intervalo', unidade: s.unidade, intervalo: s.intervalo_segundos })}>Ajustar intervalo</button>
          <button className="ui-button ui-button-secondary" onClick={() => setAcao({ id: s.id, tipo: 'renovar', unidade: s.unidade })}>Renovar vínculo</button><button className="ui-button ui-button-secondary" disabled={!s.credencial_ativa} onClick={() => setAcao({ id: s.id, tipo: 'revogar', unidade: s.unidade })}>Revogar vínculo</button></div>
      </article>)}</div>
      {selecionado && <CadastrosUnidade key={selecionado} servidorId={selecionado} EditorFormulario={EditorFormulario} />}
    </>}
    {acao && <div className="fixed inset-0 z-50 grid items-center overflow-y-auto bg-slate-950/50 p-4" role="dialog" aria-modal="true" aria-labelledby="titulo-acao-unidade"><form onSubmit={executar} className="mx-auto w-full max-w-lg space-y-4 rounded-2xl bg-white p-6"><h2 id="titulo-acao-unidade" className="text-xl font-bold">{acao.tipo === 'ativar' ? 'Ativar operação local' : acao.tipo === 'intervalo' ? 'Ajustar intervalo' : acao.tipo === 'renovar' ? 'Renovar vínculo' : 'Revogar vínculo'} · {acao.unidade}</h2>
      {acao.tipo === 'intervalo' && <label className="text-sm font-semibold">Intervalo sem pendências (segundos)<input className={CAMPO} required type="number" min={15} max={3600} value={acao.intervalo} onChange={e => setAcao({ ...acao, intervalo: Number(e.target.value) })} /></label>}
      <p className="text-sm">{acao.tipo === 'ativar' ? 'A partir desta transferência, o central deixa de receber novos pedidos desta unidade. Confirme a instalação local e a conclusão das filas anteriores.' : 'Esta ação altera a sincronização. O atendimento permanece no servidor da unidade; a escrita não será devolvida ao central.'}</p>
      <label className="block text-sm font-semibold">Motivo<textarea className={CAMPO} required minLength={8} maxLength={500} rows={3} value={motivo} onChange={e => setMotivo(e.target.value)} /></label>{erro && <p role="alert" className="text-red-800">{erro}</p>}<div className="flex gap-2"><button disabled={ocupado} className="ui-button ui-button-primary">Confirmar</button><button type="button" disabled={ocupado} className="ui-button ui-button-secondary" onClick={() => { setAcao(null); setMotivo('') }}>Voltar</button></div>
    </form></div>}
  </div>
}
