# Image for running the main app
# Declare default PHP version before FROM
ARG PHP_VERSION=8.5

# Choose our base image
FROM serversideup/php:${PHP_VERSION}-fpm-apache-ffmpeg-wpcli

# Arguments coming from docker-compose to handle permissions dynamically
ARG USER_ID
ARG GROUP_ID

# Switch to root to perform system-level configuration
USER root

# --- USER SYNC ---
# 1. Update www-data UID and GID to match the host user (e.g., 1002)
# 2. Use find to reassign ownership of existing files from the old ID (33) to the new one
RUN usermod -u ${USER_ID} www-data && \
    groupmod -g ${GROUP_ID} www-data && \
    [ -d "/var/www" ] && find /var/www -user 33 -exec chown -h www-data {} \; || true
# -----------------

# --- APP INITIALIZATION ---
# Copy the initialization script to run on startup
# Auto-generates healthcheck.php
COPY docker/scripts/init-app.sh /etc/entrypoint.d/99-init-app.sh
RUN chmod +x /etc/entrypoint.d/99-init-app.sh
# -----------------

# Install required PHP extensions with root permissions
RUN install-php-extensions exif imagick gd intl

# Download and install WP-CLI (WordPress Command Line Interface)
RUN curl -O https://raw.githubusercontent.com/wp-cli/builds/gh-pages/phar/wp-cli.phar && \
    chmod +x wp-cli.phar && \
    mv wp-cli.phar /usr/local/bin/wp

# Ensure WP-CLI cache directory exists and has correct ownership
RUN mkdir -p /var/www/.wp-cli/cache && \
    chown -R www-data:www-data /var/www/.wp-cli

# Install FFmpeg for media processing
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# IMPORTANT: We do NOT use "USER www-data" here.
# Leaving the user as root allows the entrypoint script to configure Apache modules
# and symlinks. The image will automatically drop privileges to www-data for PHP-FPM.
