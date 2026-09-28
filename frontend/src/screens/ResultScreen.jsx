import Confetti from "../components/Confetti";
import Feedback from "../components/Feedback";
import Raccoon from "../components/Raccoon";
import XpBar from "../components/XpBar";
import { difficultyTitle, levelProgress, peppers, perLevelFrom } from "../lib/game";

function XpProgress({ result, perLevel }) {
  const before = levelProgress(Math.max(0, result.xp - result.xp_gained), perLevel);
  const after = levelProgress(result.xp, perLevel);
  if (after.max) return <div className="maxlvl">⭐ Максимальный уровень · {result.xp} XP</div>;
  return (
    <div className="lvlup xpbox">
      <div className="xprow">
        <span>До уровня {after.level + 1}</span>
        <span>
          {result.xp} / {after.next} XP
        </span>
      </div>
      <XpBar pct={after.pct} from={before.level === after.level ? before.pct : 0} />
    </div>
  );
}

export default function ResultScreen({ result, difficulty, userBefore, onContinue }) {
  const win = result.outcome === "success";

  return (
    <main className={`screen result ${win ? "win" : "lose"}`}>
      {win && <Confetti />}
      <div className="spacer" style={{ maxHeight: 12 }} />
      <Raccoon className="bob" size={104} mood={win ? "happy" : "sad"} cheer={win} />
      <h1>{win ? "ПОБЕДА!" : "ПОРАЖЕНИЕ"}</h1>

      <div className="score">
        <div className="sc xp">
          <span>Опыт</span>
          <b>+{result.xp_gained}</b>
        </div>
        {win && result.score != null && (
          <div className="sc grade">
            <span>Оценка</span>
            <b>{result.score}/10</b>
          </div>
        )}
        <div className="sc foe-lvl">
          <span>Соперник</span>
          <b>{peppers(difficulty)}</b>
        </div>
      </div>

      <Feedback feedback={result.feedback} />

      {result.level_up ? (
        <div className="lvlbanner fade-in">
          ⭐ Новый уровень {result.level}!<small>Открыта сложность «{difficultyTitle(result.level)}»</small>
        </div>
      ) : (
        <XpProgress result={result} perLevel={perLevelFrom(userBefore)} />
      )}

      <div className="spacer" />
      <div className="cta-bar">
        <button type="button" className={`btn${win ? " green" : ""}`} onClick={onContinue}>
          Продолжить
        </button>
      </div>
    </main>
  );
}
