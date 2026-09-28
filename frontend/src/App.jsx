import { useEffect, useState } from "react";
import Raccoon from "./components/Raccoon";
import { consumeAuthHash, supabase } from "./lib/supabase";
import LoginScreen from "./screens/LoginScreen";
import ProfileScreen from "./screens/ProfileScreen";
import SetupScreen from "./screens/SetupScreen";
import ArenaScreen from "./screens/ArenaScreen";
import ResultScreen from "./screens/ResultScreen";

export default function App() {
  const [session, setSession] = useState(undefined); // undefined — ещё не знаем
  const [authError, setAuthError] = useState(null);
  const [screen, setScreen] = useState("profile");
  const [user, setUser] = useState(null);
  const [battle, setBattle] = useState(null);
  const [result, setResult] = useState(null);

  useEffect(() => {
    const { data } = supabase.auth.onAuthStateChange((_event, s) => setSession(s));
    (async () => {
      const err = await consumeAuthHash();
      if (err) setAuthError(err);
      const { data: current } = await supabase.auth.getSession();
      setSession(current.session);
    })();
    return () => data.subscription.unsubscribe();
  }, []);

  const userId = session?.user?.id ?? session?.access_token ?? null;
  useEffect(() => {
    // Новый вход (или выход) — всё игровое состояние с нуля.
    setUser(null);
    setBattle(null);
    setResult(null);
    setScreen("profile");
  }, [userId]);

  if (session === undefined) {
    return (
      <div className="app">
        <main className="screen center-screen">
          <Raccoon className="bob" size={110} />
        </main>
      </div>
    );
  }

  if (!session) return <LoginScreen authError={authError} />;

  const toProfile = () => {
    setBattle(null);
    setResult(null);
    setScreen("profile");
  };

  return (
    <div className="app">
      {screen === "profile" && (
        <ProfileScreen
          key={userId}
          user={user}
          needsEnsure={!user}
          onUser={setUser}
          onArena={() => setScreen("setup")}
        />
      )}
      {screen === "setup" && (
        <SetupScreen
          user={user}
          onUser={setUser}
          onBack={toProfile}
          onStart={(start, difficulty) => {
            setBattle({ start, difficulty });
            setScreen("arena");
          }}
        />
      )}
      {screen === "arena" && battle && (
        <ArenaScreen
          battle={battle}
          onExit={toProfile}
          onFinish={(res) => {
            setResult(res);
            setScreen("result");
          }}
        />
      )}
      {screen === "result" && result && (
        <ResultScreen result={result} difficulty={battle.difficulty} userBefore={user} onContinue={toProfile} />
      )}
    </div>
  );
}
