# Contrato: interfaces Python (domínio do MCP e agente)

Fonte: contratos §4 e §6. Assinaturas exatas que outros ciclos importam.

## `bussola_mcp.dominio.interfaces`

```python
class RepositorioFinanceiro(Protocol):          # @runtime_checkable
    def usuario_existe(self, id_usuario: str) -> bool: ...
    def perfil_mensal(self, id_usuario: str, ate_anomes: int) -> list[PerfilMes]: ...
    def gastos_categoria(self, id_usuario: str, ate_anomes: int,
                         desde_anomes: int | None = None) -> list[GastoCategoria]: ...
    def entradas_categoria(self, id_usuario: str, ate_anomes: int) -> list[EntradaCategoria]: ...
    def recorrentes(self, id_usuario: str, ate_anomes: int) -> list[Recorrente]: ...
    def parcelas(self, id_usuario: str, ate_anomes: int) -> list[Parcela]: ...
    def categorias(self) -> list[Categoria]: ...
    def referencia_coorte(self, faixa_renda: str, macro: str | None = None) -> list[RefCoorte]: ...

class BuscadorContexto(Protocol):               # @runtime_checkable
    def buscar(self, id_usuario: str, pergunta: str, k: int,
               ate_anomes: int) -> list[Trecho]: ...
```

`bussola_mcp.dominio.fakes`:

- `RepositorioFake(dir_fixtures: Path | str | None = None)`.
- `BuscadorFake(dir_fixtures: Path | str | None = None)`.
- `None` resolve para `<raiz do repo>/contracts/fixtures`.
- `faixa_renda_de(id_usuario) -> str | None` (acréscimo ao fake) lê
  `usuarios.json`.

## `bussola_agent.callbacks`

```python
FASES = ("before_model", "after_model", "before_tool", "after_tool")
def registrar(fase: str, funcao: Callable[..., Any], ordem: int) -> None
async def before_model(callback_context, llm_request)
async def after_model(callback_context, llm_response)
async def before_tool(tool, args, tool_context)
async def after_tool(tool, args, tool_context, tool_response)
def limpar() -> None                             # só para testes
```

## `bussola_agent.extensoes`

```python
def registrar_ferramenta(fn: Callable, sensivel: bool = False) -> None
def registrar_instrucao(ordem: int, texto: str) -> None
def ferramentas() -> list[Callable]
def ferramentas_sensiveis() -> set[str]          # acréscimo: nomes marcados sensíveis
def instrucoes() -> str
def carregar_extensoes() -> None
def limpar() -> None                             # só para testes
```

## `bussola_agent.persistencia`

```python
class RegistroApp(Protocol):                     # @runtime_checkable
    def registrar_plano(self, plano: Plano) -> str: ...
    def registrar_consentimento(self, c: Consentimento) -> str: ...
    def registrar_evento(self, e: EventoAuditoria) -> str: ...
    def registrar_acompanhamento(self, a: Acompanhamento) -> None: ...
    def obter_plano(self, plano_id: str) -> Plano | None: ...

class RegistroEmMemoria:  # implementa RegistroApp; listas planos/consentimentos/eventos/acompanhamentos
```

## `bussola_agent.mcp_conexao`

```python
def criar_toolset(url: str | None = None, usar_oidc: bool | None = None,
                  tool_filter: list[str] | None = None) -> McpToolset
def aplicar_escopo(args: dict, state: Mapping) -> dict   # força id_usuario/ate_anomes
async def chamar_ferramenta(nome: str, args: dict, state: dict,
                            url: str | None = None, usar_oidc: bool | None = None) -> dict
```

- `url` = `MCP_URL` (padrão `http://localhost:8080/mcp`).
- `usar_oidc` = `MCP_USE_OIDC == "TRUE"`.
- `chamar_ferramenta` devolve o envelope da ferramenta. Uma falha de
  transporte vira `{"erro": {"codigo": "INDISPONIVEL", ...}}`.
