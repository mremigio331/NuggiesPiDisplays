import React, { createContext, useContext, useEffect, useReducer } from "react";
import { useLocation } from "react-router-dom";
import { v4 as uuidv4 } from "uuid";

const Ctx = createContext();

export const N = {
  INFO: "info",
  SUCCESS: "success",
  ERROR: "error",
  WARNING: "warning",
  PUSH: "push",
  DISMISS: "dismiss",
  UPDATE: "update",
  CLEAR_ROUTE: "clear-route",
};

const reducer = (state, { type, payload }) => {
  switch (type) {
    case N.PUSH:
      return [...state, { ...payload, id: payload.id || uuidv4(), dismissLabel: "Dismiss" }];
    case N.DISMISS:
      return state.filter((n) => n.id !== payload);
    case N.UPDATE:
      return state.map((n) => (n.id === payload.id ? { ...n, ...payload.content } : n));
    case N.CLEAR_ROUTE:
      return state.filter((n) => n.persistent || n.pathKey === payload);
    default:
      return state;
  }
};

export const NotificationsProvider = ({ children }) => {
  const location = useLocation();
  const [notifications, dispatch] = useReducer(reducer, []);
  useEffect(() => {
    dispatch({ type: N.CLEAR_ROUTE, payload: location.key });
  }, [location]);
  return <Ctx.Provider value={[notifications, dispatch]}>{children}</Ctx.Provider>;
};

export const getNotificationsContext = () => {
  const [notifications, dispatch] = useContext(Ctx);
  const location = useLocation();

  const pushNotification = (msg) =>
    dispatch({ type: N.PUSH, payload: { ...msg, pathKey: location.key } });

  const dismissNotification = (id) => dispatch({ type: N.DISMISS, payload: id });

  const modifyNotificationContent = (id, content) =>
    dispatch({ type: N.UPDATE, payload: { id, content } });

  return { notifications, pushNotification, dismissNotification, modifyNotificationContent };
};
