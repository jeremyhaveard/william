import {
  CognitoUserPool,
  CognitoUser,
  AuthenticationDetails,
} from 'amazon-cognito-identity-js'
import { cognitoConfig, AUTH_ENABLED } from './config'

const userPool = AUTH_ENABLED
  ? new CognitoUserPool({
      UserPoolId: cognitoConfig.userPoolId,
      ClientId:   cognitoConfig.clientId,
    })
  : null

// ── Sign in ───────────────────────────────────────────────────
// Returns { idToken, accessToken, refreshToken, user }
export function signIn(email, password) {
  return new Promise((resolve, reject) => {
    if (!userPool) return reject(new Error('Auth not configured'))

    const authDetails = new AuthenticationDetails({
      Username: email,
      Password: password,
    })
    const cognitoUser = new CognitoUser({
      Username: email,
      Pool: userPool,
    })

    cognitoUser.authenticateUser(authDetails, {
      onSuccess(session) {
        resolve({
          idToken:      session.getIdToken().getJwtToken(),
          accessToken:  session.getAccessToken().getJwtToken(),
          refreshToken: session.getRefreshToken().getToken(),
          user: {
            email,
            sub: session.getIdToken().payload.sub,
          },
        })
      },
      onFailure(err) {
        reject(err)
      },
      newPasswordRequired(_userAttributes) {
        reject(new Error('PASSWORD_RESET_REQUIRED'))
      },
    })
  })
}

// ── Sign out ──────────────────────────────────────────────────
export function signOut() {
  const user = userPool?.getCurrentUser()
  if (user) user.signOut()
}

// ── Get current session (restores from localStorage) ─────────
// Returns the idToken string or null
export function getIdToken() {
  return new Promise((resolve) => {
    if (!userPool) return resolve(null)
    const user = userPool.getCurrentUser()
    if (!user) return resolve(null)

    user.getSession((err, session) => {
      if (err || !session?.isValid()) return resolve(null)
      resolve(session.getIdToken().getJwtToken())
    })
  })
}

// ── Get current user info from stored session ─────────────────
export function getCurrentUser() {
  return new Promise((resolve) => {
    if (!userPool) return resolve(null)
    const user = userPool.getCurrentUser()
    if (!user) return resolve(null)

    user.getSession((err, session) => {
      if (err || !session?.isValid()) return resolve(null)
      const payload = session.getIdToken().payload
      resolve({ email: payload.email, sub: payload.sub })
    })
  })
}
