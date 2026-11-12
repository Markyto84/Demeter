import { useCallback, useEffect, useState } from 'react'
import { api } from '../services/api.js'
import { useAuth } from '../context/auth.js'

const CAMPO = 'mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2'
const dataHora = valor => valor ? new Date(valor.endsWith('Z') || /[+-]\d\d:\d\d$/.test(valor) ? valor : valor + 'Z').toLocaleString('pt-BR') : 'Aguardando conexão'
const mensagem = e => typeof e.response?.data?.detail === 'string' ? e.response.data.detail : 'Não foi possível enviar a alteração. Confira os campos e tente novamente.'

export default function CadastrosUnidade({ servidorId, EditorFormulario }) {
  const { usuario } = useAuth()
  const [estado, setEstado] = useState(null)
  const [entidade, setEntidade] = useState('dieta:nova')
  const [dados, setDados] = useState({ nome: '', descricao: '', severa: false, ativa: true })
  const [motivo, setMotivo] = useState('')
  const [erro, setErro] = useState('')
  const [sucesso, setSucesso] = useState('')
  const [enviando, setEnviando] = useState(false)
  const [baseEdicao, setBaseEdicao] = useState(null)
  const carregar = useCallback(async () => {
    try { setEstado((await api.get(`/rede/cadastros/${servidorId}`)).data) }
    catch (e) { setErro(mensagem(e)) }
  }, [servidorId])
  useEffect(() => { Promise.resolve().then(carregar) }, [carregar])

  function selecionar(chave) {
    setEntidade(chave); setErro(''); setSucesso('')
    setBaseEdicao(estado.bases[chave])
    const valor = estado.cadastros[chave]
    setDados(valor ? structuredClone(valor) : chave === 'usuario:novo'
      ? { nome: '', nome_usuario: '', perfil: 'NUTRICIONISTA', origem_autenticacao: 'LOCAL', usuario_ad: null, senha: '', filial_ids: [] }
      : chave === 'prazos' ? { preparo_minutos: 30, entrega_minutos: 30 }
      : chave === 'etiquetas' ? { modelo: '', ip: null, porta: 9100, protocolo: 'ZPL', resolucao: 203, intervalo_mm: 2 }
      : { nome: '', descricao: '', severa: false, ativa: true })
  }
  async function enviar(chave = entidade, valor = dados, base = baseEdicao || estado.bases[chave]) {
    if (motivo.trim().length < 8) { setErro('Descreva o motivo da alteração com pelo menos oito caracteres.'); return false }
    setEnviando(true); setErro(''); setSucesso('')
    try {
      await api.post(`/rede/cadastros/${servidorId}`, { entidade: chave, base_sha256: base, dados: valor, motivo: motivo.trim() })
      setSucesso('Alteração enviada. A unidade confirmará a aplicação no próximo contato.'); setMotivo('')
      if (chave === 'usuario:novo') setDados(atual => ({ ...atual, senha: '' }))
      await carregar(); return true
    } catch (e) { setErro(mensagem(e)); return false }
    finally { setEnviando(false) }
  }
  const formulario = entidade.startsWith('formulario:')
  const remoto = {
    carregar: async tipo => ({ esquema_json: estado?.cadastros[`formulario:${tipo}`]?.esquema_json, atualizado_em: estado?.bases[`formulario:${tipo}`] }),
    salvar: async (tipo, valor, base) => enviar(`formulario:${tipo}`, valor, base),
  }
  function campo(chave, rotulo, tipo = 'text', obrigatorio = false) {
    return <label className="block text-sm font-semibold" key={chave}>{rotulo}<input className={CAMPO} type={tipo} required={obrigatorio}
      value={dados[chave] ?? ''} onChange={e => setDados(atual => ({ ...atual, [chave]: tipo === 'number' ? (e.target.value === '' ? null : Number(e.target.value)) : e.target.value }))} /></label>
  }
  const rotulo = (chave, valor) => chave === 'dieta:nova' ? 'Criar dieta' : chave === 'usuario:novo' ? 'Criar credencial'
    : chave.startsWith('dieta:') ? `Dieta · ${valor?.nome || chave}` : chave.startsWith('usuario:') ? `Credencial · ${valor?.nome || chave}`
    : chave.startsWith('formulario:') ? 'Formulários e cardápios' : ({ prazos: 'Prazos de preparo e entrega', impressora: 'Impressora de filipetas', etiquetas: 'Impressora de etiquetas' })[chave]

  return <section className="space-y-4 rounded-xl bg-panel p-5">
    <div className="flex flex-wrap items-center justify-between gap-3"><div><p className="eyebrow">Gestão compartilhada</p><h2 className="mt-2 text-xl font-bold">Cadastros da unidade</h2></div>
      <button className="ui-button ui-button-secondary" onClick={carregar}>Atualizar cadastros</button></div>
    <p className="text-sm text-slate-700">Você e a equipe local podem fazer alterações. O recebimento pela unidade confirma a publicação. Em caso de conflito, revise os dados e envie uma nova proposta.</p>
    {erro && <p role="alert" className="rounded-lg bg-red-50 p-3 text-red-900">{erro}</p>}
    {sucesso && <p role="status" className="rounded-lg bg-emerald-50 p-3 text-emerald-950">{sucesso}</p>}
    {!estado ? <p>Carregando cadastros…</p> : !Object.keys(estado.cadastros).length ? <p>Aguardando a primeira conexão do servidor da unidade.</p> : <>
      <p className="text-sm text-slate-600">Última versão recebida: {dataHora(estado.recebidos_em)}</p>
      <label className="block text-sm font-semibold">Cadastro<select className={CAMPO} value={entidade} onChange={e => selecionar(e.target.value)}>
        {Object.entries(estado.cadastros).filter(([k]) => k !== 'formulario:MEDICO').map(([chave, valor]) => <option key={chave} value={chave}>{rotulo(chave, valor)}</option>)}
      </select></label>
      <label className="block text-sm font-semibold">Motivo da alteração<textarea className={CAMPO} value={motivo} maxLength={500} minLength={8} rows={2} onChange={e => setMotivo(e.target.value)} /></label>
      {formulario && EditorFormulario ? <EditorFormulario key={servidorId} remoto={remoto} /> : <form className="grid gap-3 sm:grid-cols-2" onSubmit={e => { e.preventDefault(); enviar() }}>
        {entidade.startsWith('dieta:') && <>{campo('nome', 'Nome da dieta', 'text', true)}{campo('descricao', 'Descrição')}
          <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={!!dados.severa} onChange={e => setDados({ ...dados, severa: e.target.checked })} />Dieta com restrição severa</label>
          <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={!!dados.ativa} onChange={e => setDados({ ...dados, ativa: e.target.checked })} />Dieta ativa</label></>}
        {entidade === 'prazos' && <>{campo('preparo_minutos', 'Preparo (minutos; vazio desativa)', 'number')}{campo('entrega_minutos', 'Entrega (minutos; vazio desativa)', 'number')}</>}
        {entidade === 'impressora' && campo('ip_impressora', 'IP da impressora de filipetas')}
        {entidade === 'etiquetas' && <>{campo('modelo', 'Modelo da impressora')}{campo('ip', 'IP da impressora')}{campo('porta', 'Porta', 'number')}
          <label className="text-sm font-semibold">Protocolo<select className={CAMPO} value={dados.protocolo} onChange={e => setDados({ ...dados, protocolo: e.target.value })}><option>ZPL</option><option>TSPL</option></select></label>
          <label className="text-sm font-semibold">Resolução<select className={CAMPO} value={dados.resolucao} onChange={e => setDados({ ...dados, resolucao: Number(e.target.value) })}><option value={203}>203 dpi</option><option value={300}>300 dpi</option></select></label>{campo('intervalo_mm', 'Intervalo entre etiquetas (mm)', 'number')}</>}
        {entidade.startsWith('usuario:') && usuario.perfil === 'ADMIN_TI' && <>{campo('nome', 'Nome completo', 'text', true)}
          <label className="text-sm font-semibold">Usuário<input className={CAMPO} value={dados.nome_usuario || ''} required disabled={entidade !== 'usuario:novo'} onChange={e => setDados({ ...dados, nome_usuario: e.target.value })} /></label>
          <label className="text-sm font-semibold">Perfil<select className={CAMPO} value={dados.perfil || 'NUTRICIONISTA'} onChange={e => setDados({ ...dados, perfil: e.target.value })}>{[['NUTRICIONISTA', 'Gestão de nutrição'], ['ADMIN_TI', 'Administrador de TI'], ['COZINHA', 'Cozinha'], ['COPEIRA', 'Copeira']].map(([id, nome]) => <option key={id} value={id}>{nome}</option>)}</select></label>
          {entidade === 'usuario:novo' ? <>{campo('senha', 'Senha temporária (8–12 caracteres)', 'password', true)}<p className="text-xs text-slate-600 sm:col-span-2">Conta local com troca obrigatória no primeiro acesso. Maiúscula, número e caractere especial são obrigatórios. Vínculos com AD são configurados diretamente na unidade.</p></>
            : <label className="flex items-center gap-2"><input type="checkbox" checked={!!dados.ativo} onChange={e => setDados({ ...dados, ativo: e.target.checked })} />Conta ativa</label>}</>}
        <button disabled={enviando} className="ui-button ui-button-primary sm:col-span-2">{enviando ? 'Enviando…' : 'Enviar alteração à unidade'}</button>
      </form>}
      <div className="space-y-2 border-t border-slate-200 pt-4"><h3 className="font-bold">Acompanhamento das alterações</h3>
        {!estado.alteracoes.length && <p className="text-sm text-slate-600">Nenhuma alteração enviada pela central.</p>}
        {estado.alteracoes.map(c => <article key={c.id} className="rounded-lg bg-white p-3 text-sm"><div className="flex flex-wrap justify-between gap-2"><strong>{rotulo(c.entidade, estado.cadastros[c.entidade]) || c.entidade}</strong><span className={c.estado === 'CONFLITO' ? 'font-bold text-red-800' : 'font-semibold text-brand'}>{c.estado === 'APLICADA' ? 'Aplicada na unidade' : c.estado === 'CONFLITO' ? 'Revisão necessária' : 'Aguardando unidade'}</span></div><p>{c.autor_nome} · {dataHora(c.criado_em)}</p><p>{c.motivo}</p>{c.resultado && <p className="mt-1">{c.resultado}</p>}</article>)}
      </div>
    </>}
  </section>
}
