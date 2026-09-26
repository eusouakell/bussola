interface Props {
  texto: string;
}

export function MensagemCliente({ texto }: Props) {
  return (
    <div className="msg-client">
      <span className="sr-only">Você: </span>
      {texto}
    </div>
  );
}
