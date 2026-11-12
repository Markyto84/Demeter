"""Protege identidade, segredo e papel nas operações do instalador."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from uuid import uuid4

from configurar_servidor import configurar, ler_configuracao


class InstalacaoUnidadesTest(unittest.TestCase):
    def test_rotacao_preserva_identidade_e_nao_permite_reutilizar_outro_vinculo(self):
        with TemporaryDirectory() as pasta:
            raiz = Path(pasta)
            bundle = raiz / 'entrada.json'
            dados = dict(protocolo=1, servidor_id=str(uuid4()), central_url='https://central.example.test', token='FICTICIO-' * 8, geracao=1, intervalo_segundos=60)
            bundle.write_text(json.dumps(dados))
            configurar(raiz, 'http://192.0.2.10', modo='unidade', vinculo=bundle)
            local = raiz / 'work/unidade/vinculo.json'
            primeiro = json.loads(local.read_text())
            ambiente = (raiz / '.env').read_bytes()
            dados['token'] = 'NOVO-FICTICIO-' * 5
            bundle.write_text(json.dumps(dados))
            configurar(raiz, 'https://unidade.example.test', modo='unidade', vinculo=bundle, alterar=True)
            segundo = json.loads(local.read_text())
            self.assertEqual(primeiro['instalacao_uuid'], segundo['instalacao_uuid'])
            self.assertNotEqual(primeiro['token'], segundo['token'])
            self.assertEqual((raiz / '.env').read_bytes(), ambiente)
            with self.assertRaises(ValueError): configurar(raiz, 'https://unidade.example.test', modo='central', alterar=True)
            dados['servidor_id'] = str(uuid4()); bundle.write_text(json.dumps(dados))
            with self.assertRaises(ValueError): configurar(raiz, 'https://unidade.example.test', modo='unidade', vinculo=bundle, alterar=True)
            self.assertEqual(json.loads(local.read_text()), segundo)

    def test_central_exige_https_e_vinculo_invalido_nao_cria_segredos(self):
        with TemporaryDirectory() as pasta:
            raiz = Path(pasta)
            with self.assertRaises(ValueError): configurar(raiz, 'http://192.0.2.10', modo='central')
            with self.assertRaises(ValueError): configurar(raiz, 'http://192.0.2.10', modo='unidade')
            self.assertEqual(list(raiz.iterdir()), [])
            configurar(raiz, 'https://central.example.test', modo='central')
            self.assertEqual(ler_configuracao(raiz / 'work/servidor.env')['MODO_SERVIDOR'], 'CENTRAL')
