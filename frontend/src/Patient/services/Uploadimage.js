import axios from 'axios';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8092/api';

const upload = async (formData) => {
  try {
    const token = localStorage.getItem('token');
    const response = await axios.post(`${API_URL}/image/upload`, formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
        'Authorization': `Bearer ${token}`
      },
    });
    return response;
  } catch (error) {
    console.error('Error uploading image:', error);
    throw error;
  }
};

export default {
  upload,
};
