@echo off
rem Starts the dev server with a tunnel so a phone on any network can open the app in Expo Go.
rem Extra options pass through, e.g. ".\phone --no-dev --minify" to feel production speed.
rem Reads EXPO_TOKEN from your Windows user settings (set once with: setx EXPO_TOKEN "your-token").
for /f "tokens=2,*" %%a in ('reg query HKCU\Environment /v EXPO_TOKEN 2^>nul ^| find "EXPO_TOKEN"') do set "EXPO_TOKEN=%%b"
if not defined EXPO_TOKEN (
  echo EXPO_TOKEN is not set. Create a token on expo.dev and run: setx EXPO_TOKEN "your-token"
  exit /b 1
)
call npx expo whoami
npx expo start --tunnel %*
