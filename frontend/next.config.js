const path = require('path');

/** @type {import('next').NextConfig} */
const withPWA = require('next-pwa')({
  dest: 'public',
  disable: process.env.NODE_ENV === 'development',
});

const nextConfig = {
  reactStrictMode: true,
  swcMinify: true,
  webpack(config) {
    config.watchOptions = {
      poll: 1000, // Check for changes every second
      aggregateTimeout: 300, // Delay before rebuilding
    }
    config.resolve.alias['@'] = path.join(__dirname, 'src');
    return config;
  },
};

module.exports = withPWA(nextConfig);