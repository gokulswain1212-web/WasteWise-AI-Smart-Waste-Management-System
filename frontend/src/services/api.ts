import axios from "axios";

const api = axios.create({
  baseURL: "",
  timeout: 15000,
  withCredentials: true,
});

export default api;
