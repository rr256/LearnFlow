import nextCoreWebVitals from "eslint-config-next/core-web-vitals";
import nextTypeScript from "eslint-config-next/typescript";

/**
 * ESLint flat configuration.
 *
 * `core-web-vitals` carries the accessibility rules from eslint-plugin-jsx-a11y
 * alongside the Next.js and React rules, so the curriculum view's markup is
 * linted for accessibility rather than only reviewed for it.
 */
const config = [
  {
    ignores: ["node_modules/**", ".next/**", "next-env.d.ts"],
  },
  ...nextCoreWebVitals,
  ...nextTypeScript,
];

export default config;
