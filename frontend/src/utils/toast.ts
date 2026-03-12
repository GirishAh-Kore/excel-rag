// Simple toast notification utility
// In a production app, you might use a library like react-toastify or notistack

export type ToastType = 'success' | 'error' | 'info' | 'warning';

export const showToast = (message: string, type: ToastType = 'info') => {
  // For now, just use console and alert
  // This can be replaced with a proper toast library
  console.log(`[${type.toUpperCase()}] ${message}`);
  
  if (type === 'error') {
    // Only show alerts for errors to avoid being too intrusive
    alert(message);
  }
};

export const toast = {
  success: (message: string) => showToast(message, 'success'),
  error: (message: string) => showToast(message, 'error'),
  info: (message: string) => showToast(message, 'info'),
  warning: (message: string) => showToast(message, 'warning'),
};
