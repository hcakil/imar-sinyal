import { cert, getApps, initializeApp } from "firebase-admin/app";
import { getFirestore, type Firestore } from "firebase-admin/firestore";

let cached: Firestore | null | undefined;

export function firestoreDb(): Firestore | null {
  if (cached !== undefined) return cached;

  const projectId =
    process.env.GOOGLE_CLOUD_PROJECT || process.env.FIREBASE_PROJECT_ID;
  if (!projectId) {
    cached = null;
    return cached;
  }

  if (!getApps().length) {
    const clientEmail = process.env.FIREBASE_CLIENT_EMAIL;
    const privateKey = process.env.FIREBASE_PRIVATE_KEY?.replace(/\\n/g, "\n");
    initializeApp(
      clientEmail && privateKey
        ? {
            credential: cert({ projectId, clientEmail, privateKey }),
            projectId,
          }
        : { projectId },
    );
  }

  cached = getFirestore();
  return cached;
}
