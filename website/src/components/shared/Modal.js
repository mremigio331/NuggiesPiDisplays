import React from "react";
import { createPortal } from "react-dom";

export default function Modal({ visible, header, children, footer, onDismiss }) {
  if (!visible) return null;
  return createPortal(
    <div
      className="m-modal-overlay"
      onClick={(e) => {
        if (e.target === e.currentTarget) onDismiss?.();
      }}
    >
      <div className="m-modal">
        {header && <div className="m-modal-header">{header}</div>}
        <div className="m-modal-body">{children}</div>
        {footer && <div className="m-modal-footer">{footer}</div>}
      </div>
    </div>,
    document.body
  );
}
