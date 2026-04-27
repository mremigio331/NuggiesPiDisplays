import * as React from "react";
import { Cards, Box, Header, SpaceBetween } from "@cloudscape-design/components";
import { TrainLogos } from "../../utility/SubwayLogos";

const timeColor = (mins) => (mins === 0 ? "#f0ab00" : "#1d8348");
const timeLabel = (mins) => (mins === 0 ? "Now" : `${mins} min`);

export default function TrainCards({ trains, isMobile }) {
  const size = isMobile ? "15" : "25";
  return (
    <Cards
      cardDefinition={{
        header: (train) => (
          <Header
            variant="h4"
            actions={
              <Box fontSize={isMobile ? "body-s" : "heading-l"} fontWeight="bold" color="inherit">
                <span style={{ color: timeColor(train.arrival_minutes) }}>
                  {timeLabel(train.arrival_minutes)}
                </span>
              </Box>
            }
          >
            <SpaceBetween direction="horizontal" size="s" alignItems="center">
              {TrainLogos[train.route] && (
                <img width={size} height={size} src={TrainLogos[train.route]} alt={train.route} />
              )}
              <span style={{ color: timeColor(train.arrival_minutes) }}>{train.destination}</span>
            </SpaceBetween>
          </Header>
        ),
      }}
      cardsPerRow={[{ cards: 1 }]}
      items={trains}
    />
  );
}
