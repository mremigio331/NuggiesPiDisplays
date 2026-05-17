import React from "react";

export default function LoadingSpinner() {
  return (
    <div style={{ display: "flex", justifyContent: "center", padding: 40 }}>
      <div className="m-spinner m-spinner-lg" />
    </div>
  );
}
