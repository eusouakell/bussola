-- Bússola 001: seed versionado de bussola_dados.categorias (contratos §3; ciclo 001 §3.1).
-- As 98 combinações macro/micro de hackathon_dados.extrato_sintetico (2025), uma por linha.
--
-- Discricionárias (INFERRED, pendente de revisão humana; ciclo 001 §10 e plan.md D-06):
-- - 0.5: Assinaturas e Delivery (corte fácil, sem perda de bem-estar essencial);
-- - 0.3: restaurantes e comer fora (exceto padaria), lazer (exceto associações e clubes)
--        e compras/vestuário/artigos esportivos/móveis em Lojas e sites;
-- - 0.2: padaria, associações e clubes, brinquedos e artigos infantis e todas as
--        micros de Viagens.
-- Todas as demais (moradia, mercado, saúde, educação, transporte, dívidas, tarifas,
-- impostos, transferências, saques e entradas) têm discricionaria = FALSE e
-- corte_max_pct = 0.0.

BEGIN TRANSACTION;

TRUNCATE TABLE {{dataset}}.categorias;

INSERT INTO {{dataset}}.categorias (macro, micro, discricionaria, corte_max_pct)
VALUES
  -- Assinaturas
  ('Assinaturas', 'Assinaturas', TRUE, 0.5),
  -- Beneficios
  ('Beneficios', 'Beneficio INSS', FALSE, 0.0),
  -- Boletos diversos
  ('Boletos diversos', 'Boleto', FALSE, 0.0),
  -- Casa
  ('Casa', 'Agua e esgoto', FALSE, 0.0),
  ('Casa', 'Celular', FALSE, 0.0),
  ('Casa', 'Condominio', FALSE, 0.0),
  ('Casa', 'Empregados domesticos', FALSE, 0.0),
  ('Casa', 'Energia eletrica', FALSE, 0.0),
  ('Casa', 'Gas', FALSE, 0.0),
  ('Casa', 'IPTU', FALSE, 0.0),
  ('Casa', 'Jardinagem', FALSE, 0.0),
  ('Casa', 'Lavanderia', FALSE, 0.0),
  ('Casa', 'Outras contas', FALSE, 0.0),
  ('Casa', 'Outras despesas de moradia', FALSE, 0.0),
  ('Casa', 'Pagamento de aluguel', FALSE, 0.0),
  ('Casa', 'Seguro residencial', FALSE, 0.0),
  ('Casa', 'TV Internet celular e telefone', FALSE, 0.0),
  -- Cuidados pessoais
  ('Cuidados pessoais', 'Outros cuidados pessoais', FALSE, 0.0),
  ('Cuidados pessoais', 'Outros esportes', FALSE, 0.0),
  ('Cuidados pessoais', 'Produtos de beleza', FALSE, 0.0),
  ('Cuidados pessoais', 'Salao de beleza ou barbearia', FALSE, 0.0),
  -- Delivery
  ('Delivery', 'Delivery', TRUE, 0.5),
  -- Educacao
  ('Educacao', 'Curso de idiomas', FALSE, 0.0),
  ('Educacao', 'Entidades de classe', FALSE, 0.0),
  ('Educacao', 'Mensalidade escolar', FALSE, 0.0),
  ('Educacao', 'Outras despesas de educacao', FALSE, 0.0),
  -- Emprestimos e financiamentos
  ('Emprestimos e financiamentos', 'Emprestimos', FALSE, 0.0),
  ('Emprestimos e financiamentos', 'Financiamento de imovel', FALSE, 0.0),
  ('Emprestimos e financiamentos', 'Outros emprestimos', FALSE, 0.0),
  -- Lazer
  ('Lazer', 'Associacoes e clubes', TRUE, 0.2),
  ('Lazer', 'Cinema', TRUE, 0.3),
  ('Lazer', 'Eletronicos', TRUE, 0.3),
  ('Lazer', 'Eventos e festas', TRUE, 0.3),
  ('Lazer', 'Ingresso de shows', TRUE, 0.3),
  ('Lazer', 'Livros musica e video', TRUE, 0.3),
  ('Lazer', 'Museu e teatro', TRUE, 0.3),
  ('Lazer', 'Outros entretenimentos', TRUE, 0.3),
  ('Lazer', 'Videogames', TRUE, 0.3),
  -- Lojas e sites
  ('Lojas e sites', 'Artigos esportivos', TRUE, 0.3),
  ('Lojas e sites', 'Brinquedos e artigos infantis', TRUE, 0.2),
  ('Lojas e sites', 'Compras', TRUE, 0.3),
  ('Lojas e sites', 'Manutencao da casa', FALSE, 0.0),
  ('Lojas e sites', 'Moveis e decoracao', TRUE, 0.3),
  ('Lojas e sites', 'Vestuario e acessorios', TRUE, 0.3),
  -- Mercado
  ('Mercado', 'Casa de Carnes', FALSE, 0.0),
  ('Mercado', 'Feira livre', FALSE, 0.0),
  ('Mercado', 'Mercado', FALSE, 0.0),
  ('Mercado', 'Outros mercados', FALSE, 0.0),
  -- Outros gastos
  ('Outros gastos', 'Cheque', FALSE, 0.0),
  ('Outros gastos', 'Contabilidade', FALSE, 0.0),
  ('Outros gastos', 'Diversos', FALSE, 0.0),
  ('Outros gastos', 'Frete e correios', FALSE, 0.0),
  ('Outros gastos', 'Multa por atraso', FALSE, 0.0),
  ('Outros gastos', 'Outras despesas com impostos', FALSE, 0.0),
  ('Outros gastos', 'Outros gastos', FALSE, 0.0),
  ('Outros gastos', 'Outros servicos', FALSE, 0.0),
  ('Outros gastos', 'Pagamento de impostos', FALSE, 0.0),
  ('Outros gastos', 'Pensao alimenticia', FALSE, 0.0),
  ('Outros gastos', 'Publicidade', FALSE, 0.0),
  -- Pets
  ('Pets', 'Outros gastos de animais', FALSE, 0.0),
  ('Pets', 'Pet shop', FALSE, 0.0),
  ('Pets', 'Veterinario', FALSE, 0.0),
  -- Posto de combustivel
  ('Posto de combustivel', 'Loja de conveniencia', FALSE, 0.0),
  ('Posto de combustivel', 'Posto de combustivel', FALSE, 0.0),
  -- Produtos financeiros
  ('Produtos financeiros', 'Anuidade e pacote de servico', FALSE, 0.0),
  ('Produtos financeiros', 'Consorcio', FALSE, 0.0),
  ('Produtos financeiros', 'Juros pagos', FALSE, 0.0),
  ('Produtos financeiros', 'Outras tarifas financeiras', FALSE, 0.0),
  ('Produtos financeiros', 'Outros seguros', FALSE, 0.0),
  ('Produtos financeiros', 'Pagamento de fatura', FALSE, 0.0),
  ('Produtos financeiros', 'Seguros', FALSE, 0.0),
  ('Produtos financeiros', 'Titulo de capitalizacao', FALSE, 0.0),
  -- Recebimentos diversos
  ('Recebimentos diversos', 'Recebimentos diversos', FALSE, 0.0),
  -- Rendimentos
  ('Rendimentos', 'Recebimento Aluguel', FALSE, 0.0),
  -- Restaurantes
  ('Restaurantes', 'Cafeteria', TRUE, 0.3),
  ('Restaurantes', 'Outras comidas e bebidas', TRUE, 0.3),
  ('Restaurantes', 'Padaria', TRUE, 0.2),
  ('Restaurantes', 'Restaurantes', TRUE, 0.3),
  -- Salarios e bonificacoes
  ('Salarios e bonificacoes', '13o salario', FALSE, 0.0),
  ('Salarios e bonificacoes', 'Bonus PLR', FALSE, 0.0),
  ('Salarios e bonificacoes', 'Salario CLT', FALSE, 0.0),
  -- Saque
  ('Saque', 'Saque', FALSE, 0.0),
  -- Transferencias diversas
  ('Transferencias diversas', 'Outras transferencias', FALSE, 0.0),
  -- Transporte por app
  ('Transporte por app', 'Transporte por app', FALSE, 0.0),
  -- Transporte publico
  ('Transporte publico', 'Passagem de onibus', FALSE, 0.0),
  ('Transporte publico', 'Transporte publico', FALSE, 0.0),
  -- Veiculos
  ('Veiculos', 'Aluguel de carro', FALSE, 0.0),
  ('Veiculos', 'Estacionamento', FALSE, 0.0),
  ('Veiculos', 'Licenciamento IPVA e DPVAT', FALSE, 0.0),
  ('Veiculos', 'Manutencao e reparo', FALSE, 0.0),
  ('Veiculos', 'Multa', FALSE, 0.0),
  ('Veiculos', 'Outros gastos com transporte', FALSE, 0.0),
  ('Veiculos', 'Pedagio', FALSE, 0.0),
  ('Veiculos', 'Seguro de automovel', FALSE, 0.0),
  -- Viagens
  ('Viagens', 'Compra de moedas', TRUE, 0.2),
  ('Viagens', 'Hospedagem', TRUE, 0.2),
  ('Viagens', 'Outros gastos de viagem', TRUE, 0.2),
  ('Viagens', 'Passagem aerea e taxas', TRUE, 0.2);

COMMIT TRANSACTION;
