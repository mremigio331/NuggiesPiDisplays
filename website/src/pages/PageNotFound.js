import * as React from "react";
import { Link } from "react-router-dom";

export default function PageNotFound() {
  return (
    <div>
      <div className="m-section-title">Page Not Found</div>
      <div className="m-card">
        Not sure how you ended up here.{" "}
        <Link to="/" style={{ color: "#4a9fe8" }}>
          Go home.
        </Link>
      </div>
    </div>
  );
}
