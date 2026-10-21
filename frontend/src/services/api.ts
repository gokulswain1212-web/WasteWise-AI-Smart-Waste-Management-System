import axios from "axios";

const api = axios.create({
  baseURL: "",
  timeout: 15000,
  withCredentials: true,
});

api.interceptors.response.use(
  (response) => response,
  (error: unknown) => {
    if (
      axios.isAxiosError(error)
      && error.response?.status === 401
      && !error.config?.url?.startsWith("/api/v1/auth/")
      && typeof window !== "undefined"
    ) {
      window.dispatchEvent(new Event("wastewise:session-expired"));
    }
    return Promise.reject(error);
  },
);

export default api;
