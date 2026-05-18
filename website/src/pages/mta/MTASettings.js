import * as React from "react";
import { useMTAConfigs } from "../../hooks/useMTAConfigs";
import { useAllStations } from "../../hooks/useAllStations";
import { useEnabledStations } from "../../hooks/useEnabledStations";
import SettingsHeader from "../../components/shared/SettingsHeader";
import LoadingSpinner from "../../components/shared/LoadingSpinner";
import StationPicker from "../../components/mta/StationPicker";
import DisplayOptions from "../../components/mta/DisplayOptions";
import StationCycleList from "../../components/mta/StationCycleList";

export default function MTASettings() {
  const { data: configs, isLoading: configsLoading } = useMTAConfigs();
  const { data: allStations, isLoading: stationsLoading } = useAllStations();
  const { data: enabledStations } = useEnabledStations();

  const isLoading = configsLoading || stationsLoading;

  return (
    <div>
      <SettingsHeader title="MTA Settings" backTo="/mta" />
      <div className="m-section-sub" style={{ marginBottom: 16 }}>
        Configure station and display options
      </div>

      {isLoading ? (
        <LoadingSpinner />
      ) : (
        <>
          <StationPicker currentStation={configs?.station} allStations={allStations} />
          <DisplayOptions configs={configs || {}} />
          <StationCycleList allStations={allStations} enabledStations={enabledStations} />
        </>
      )}
    </div>
  );
}
