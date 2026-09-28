// feedback приходит объектом (структурный разбор) или строкой, если модель не
// собрала структуру — контракт /negotiation/turn допускает оба варианта.
// React экранирует текст сам, поэтому цитата игрока (broke_quote) безопасна.
export default function Feedback({ feedback }) {
  if (!feedback) return null;
  if (typeof feedback === "string") {
    return (
      <div className="fb">
        <b>Разбор судьи</b>
        <p>{feedback}</p>
      </div>
    );
  }
  const { broke_quote, broke_reason, what_worked, alternative_phrasing, tip } = feedback;
  return (
    <div className="fb">
      <b>Разбор судьи</b>
      {(broke_quote || broke_reason) && (
        <div>
          <span className="label bad">Где сломалось:</span> {broke_reason}
          {broke_quote && <blockquote>«{broke_quote}»</blockquote>}
        </div>
      )}
      {what_worked && (
        <p>
          <span className="label good">Что сработало:</span> {what_worked}
        </p>
      )}
      {alternative_phrasing && (
        <p>
          <span className="label alt">Можно было сказать так:</span> «{alternative_phrasing}»
        </p>
      )}
      {tip && (
        <p>
          <span className="label tip">Совет:</span> {tip}
        </p>
      )}
    </div>
  );
}
