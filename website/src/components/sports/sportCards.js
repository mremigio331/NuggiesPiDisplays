/**
 * Maps a sport key to the GameCard that renders it, so a mixed-league feed (the
 * favourites scoreboard) can pick the right card per game from its `sport` tag.
 *
 * Keep in sync with the leagues in Sports.js / SportsSettings.js and the
 * backend _SPORT_CONFIG.
 */
import NBAGameCard from "./NBAGameCard";
import MLBGameCard from "./MLBGameCard";
import NHLGameCard from "./NHLGameCard";
import FootballGameCard from "./FootballGameCard";
import SoccerGameCard from "./SoccerGameCard";

export const SPORT_CARDS = {
  nba: NBAGameCard,
  wnba: NBAGameCard, // basketball shares the NBA card
  mlb: MLBGameCard,
  nhl: NHLGameCard,
  nfl: FootballGameCard,
  ncaaf: FootballGameCard,
  nwsl: SoccerGameCard,
  epl: SoccerGameCard,
  laliga: SoccerGameCard,
  bundesliga: SoccerGameCard,
};

/** GameCard component for a sport key, defaulting to the NBA card. */
export function cardForSport(sport) {
  return SPORT_CARDS[sport] ?? NBAGameCard;
}

/** Human labels per league, for headings and pickers. */
export const SPORT_LABELS = {
  mlb: "MLB",
  nba: "NBA",
  wnba: "WNBA",
  nfl: "NFL",
  ncaaf: "NCAA Football",
  nhl: "NHL",
  nwsl: "NWSL",
  epl: "Premier League",
  laliga: "La Liga",
  bundesliga: "Bundesliga",
};

/** Ordered list of real leagues (matches the display cycle order). */
export const LEAGUES = [
  "mlb",
  "nba",
  "wnba",
  "nfl",
  "ncaaf",
  "nhl",
  "nwsl",
  "epl",
  "laliga",
  "bundesliga",
];
