import t1 from "../assets/SubwaySVGs/1.svg";
import t2 from "../assets/SubwaySVGs/2.svg";
import t3 from "../assets/SubwaySVGs/3.svg";
import t4 from "../assets/SubwaySVGs/4.svg";
import t5 from "../assets/SubwaySVGs/5.svg";
import t6 from "../assets/SubwaySVGs/6.svg";
import t6d from "../assets/SubwaySVGs/6d.svg";
import t7 from "../assets/SubwaySVGs/7.svg";
import t7d from "../assets/SubwaySVGs/7d.svg";
import ta from "../assets/SubwaySVGs/a.svg";
import tb from "../assets/SubwaySVGs/b.svg";
import tc from "../assets/SubwaySVGs/c.svg";
import td from "../assets/SubwaySVGs/d.svg";
import te from "../assets/SubwaySVGs/e.svg";
import tf from "../assets/SubwaySVGs/f.svg";
import tg from "../assets/SubwaySVGs/g.svg";
import th from "../assets/SubwaySVGs/h.svg";
import tj from "../assets/SubwaySVGs/j.svg";
import tl from "../assets/SubwaySVGs/l.svg";
import tm from "../assets/SubwaySVGs/m.svg";
import tn from "../assets/SubwaySVGs/n.svg";
import tq from "../assets/SubwaySVGs/q.svg";
import tr from "../assets/SubwaySVGs/r.svg";
import ts from "../assets/SubwaySVGs/s.svg";
import tsf from "../assets/SubwaySVGs/sf.svg";
import tsir from "../assets/SubwaySVGs/sir.svg";
import tsr from "../assets/SubwaySVGs/sr.svg";
import tw from "../assets/SubwaySVGs/w.svg";
import tz from "../assets/SubwaySVGs/z.svg";

export const TrainLogos = {
  1: t1,
  2: t2,
  3: t3,
  4: t4,
  5: t5,
  6: t6,
  "6X": t6d,
  7: t7,
  "7X": t7d,
  A: ta,
  B: tb,
  C: tc,
  D: td,
  E: te,
  F: tf,
  G: tg,
  GS: tg,
  H: th,
  J: tj,
  L: tl,
  M: tm,
  N: tn,
  Q: tq,
  R: tr,
  S: ts,
  SF: tsf,
  SIR: tsir,
  SI: tsir,
  SR: tsr,
  W: tw,
  Z: tz,
};

const logoValues = Object.values(TrainLogos);

export const getRandomTrainLogos = (n = 14) => {
  const shuffled = [...logoValues].sort(() => Math.random() - 0.5);
  return shuffled.slice(0, n);
};
