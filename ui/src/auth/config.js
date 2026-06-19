// Cognito configuration — set these in ui/.env.local for local dev
// or as environment variables in your deployment pipeline.
//
// Example ui/.env.local:
//   VITE_COGNITO_USER_POOL_ID=us-east-1_XXXXXXXXX
//   VITE_COGNITO_CLIENT_ID=xxxxxxxxxxxxxxxxxxxxxxxxxx
//   VITE_AWS_REGION=us-east-1

export const cognitoConfig = {
  userPoolId: import.meta.env.VITE_COGNITO_USER_POOL_ID || '',
  clientId:   import.meta.env.VITE_COGNITO_CLIENT_ID    || '',
  region:     import.meta.env.VITE_AWS_REGION           || 'us-east-1',
}

// Auth is only enforced when Cognito is configured.
// Locally (no env vars set) the app runs without login.
export const AUTH_ENABLED = Boolean(
  cognitoConfig.userPoolId && cognitoConfig.clientId
)
