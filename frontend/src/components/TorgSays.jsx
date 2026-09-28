import Raccoon from "./Raccoon";

// Сообщение от лица енота: ошибки, отказы, подсказки.
export default function TorgSays({ children, mood = "sly", tone = "error", action }) {
  return (
    <div className={`torg-says ${tone}`} role={tone === "error" ? "alert" : "status"}>
      <Raccoon mood={mood} size={40} />
      <div className="torg-says-body">
        <p>{children}</p>
        {action}
      </div>
    </div>
  );
}
