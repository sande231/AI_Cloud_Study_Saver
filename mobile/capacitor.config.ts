import type { CapacitorConfig } from '@capacitor/cli';

const config: CapacitorConfig = {
  appId: 'com.sandeepshah.funstudy',
  appName: 'AI Cloud Study Saver',
  webDir: 'www',
  server: {
    url: 'https://ai-cloud-study-saver.onrender.com',
    cleartext: false
  },
  plugins: {
    SplashScreen: {
      launchShowDuration: 1200,
      backgroundColor: '#2563eb',
      showSpinner: false
    },
    StatusBar: {
      style: 'DARK',
      backgroundColor: '#111827'
    }
  },
  ios: {
    contentInset: 'automatic'
  },
  android: {
    allowMixedContent: false,
    captureInput: true
  }
};

export default config;
