import React, { createContext, useContext, useReducer } from "react";

export const INCREMENT_RETRIES = "INCREMENT_RETRIES";
export const RESET_RETRIES = "RESET_RETRIES";

const Ctx = createContext();

const reducer = (state, { type }) => {
  switch (type) {
    case INCREMENT_RETRIES:
      return { ...state, apiRetries: state.apiRetries + 1 };
    case RESET_RETRIES:
      return { ...state, apiRetries: 0 };
    default:
      return state;
  }
};

export const APICheckProvider = ({ children }) => {
  const [apiCheckState, dispatch] = useReducer(reducer, { apiRetries: 0 });
  return <Ctx.Provider value={{ apiCheckState, dispatch }}>{children}</Ctx.Provider>;
};

export const useApiCheck = () => {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useApiCheck must be used within APICheckProvider");
  return ctx;
};
